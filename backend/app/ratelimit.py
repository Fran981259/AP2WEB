"""Rate limiting — `limits`-backed, configurable, runtime-toggleable.

Storage is selected globally:

- ``memory`` (default in dev/test): an isolated in-memory bucket store. It is
  process-local — fine for a single dev instance, never for production.
- ``redis`` (required in production): a shared Redis storage so limits are
  enforced consistently across API replicas and survive restarts.

See `_build_storage` and ``docs/README`` "Rate limiting".
"""
from __future__ import annotations

import logging
import math
import threading
import time

from fastapi import HTTPException, Request
from limits import parse_many, storage, strategies
from limits.strategies import MovingWindowRateLimiter

from . import config
from .security import client_ip

logger = logging.getLogger("ap2web.ratelimit")


def _build_storage() -> storage.RateLimiterStorage:
    """Build one storage instance based on the configured backend.

    Redis URLs come from ``AP2WEB_REDIS_URL``; invalid configuration surfaces a
    clear error here (startup/probe time) instead of misleading 429/200.
    """
    if config.settings.rate_limit_storage == "redis":
        return storage.RedisStorage(config.settings.redis_url)
    return storage.MemoryStorage()


def _request_identity(request: Request) -> str:
    """Prefer the authenticated identity, fall back to the client IP.

    The token is decoded without signature verification purely for rate-key
    construction; auth is still enforced by the endpoint dependencies.
    The IP uses the trusted-proxy-aware ``client_ip`` (never a spoofable
    header when the peer is not an allow-listed proxy).
    """
    token = None
    auth = request.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
    if not token:
        token = request.cookies.get(config.ACCESS_COOKIE)
    if token:
        try:
            import jwt as _jwt

            payload = _jwt.decode(token, options={"verify_signature": False})
            sub = payload.get("sub")
            if sub:
                return f"user:{sub}"
        except Exception:
            pass
    return f"ip:{client_ip(request)}"


class AP2RateLimiter:
    """Thin wrapper over `limits` for endpoints with named, configurable limits."""

    def __init__(self, enabled: bool, limits: dict[str, str]):
        self._lock = threading.Lock()
        self._storage = _build_storage()
        self._strategy: MovingWindowRateLimiter = strategies.MovingWindowRateLimiter(self._storage)
        self._limits: dict[str, list] = {}
        self.enabled = enabled
        for name, spec in limits.items():
            try:
                self._limits[name] = parse_many(spec)
            except Exception:
                logger.warning("invalid rate limit spec %r for %r; disabled", spec, name)
                self._limits[name] = []

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled

    def reset(self) -> None:
        with self._lock:
            # `limits` MemoryStorage has no "clear all" API; rebuild it.
            self._storage = _build_storage()
            self._strategy = strategies.MovingWindowRateLimiter(self._storage)

    def check(self, name: str, request: Request) -> None:
        """Consume one unit of the named limit or raise HTTP 429."""
        if not self.enabled:
            return
        limits = self._limits.get(name)
        if not limits:
            return
        item = _request_identity(request)
        retry_after: float | None = None
        with self._lock:
            for lim in limits:
                stats = self._strategy.get_window_stats(lim, item)
                if stats.remaining <= 0:
                    retry_after = max(1.0, math.ceil(stats.reset_time - time.time()))
                    break
                hit_ok = self._strategy.hit(lim, item)
                if not hit_ok:
                    stats2 = self._strategy.get_window_stats(lim, item)
                    retry_after = max(1.0, math.ceil(stats2.reset_time - time.time()))
                    break
        if retry_after is not None:
            from .security import audit_ratelimit

            audit_ratelimit(request, name)
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please retry later.",
                headers={"Retry-After": str(int(retry_after))},
            )


# Module-level singleton created from the central settings.
rate_limiter = AP2RateLimiter(config.settings.rate_limit_enabled, config.settings.rate_limits)


def rate_limit(name: str):
    """Dependency factory: ``Depends(rate_limit("login"))``."""
    def _dependency(request: Request) -> None:
        rate_limiter.check(name, request)
    return _dependency