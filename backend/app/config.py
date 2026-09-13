"""Central security configuration (Phase 2 — production hardening).

All security-relevant settings live here so modules do not read raw
environment variables independently. Validation fails fast (at startup)
when production configuration is weak.
"""
from __future__ import annotations

import os

_DEV_PLACEHOLDER_SECRETS = {
    "dev-secret-change-me-please-use-env-var-0123456789abcdef",
    "change-me-in-render",
    "troque-esta-chave-por-um-valor-aleatorio-de-64-caracteres",
    "replace-with-a-random-secret-at-least-32-characters",
    "change-me",
    "secret",
    "password",
    "changeme",
    "qwerty",
    "12345678",
}

# Cookie names (kept from Phase 1 for Bearer/cookie compatibility).
ACCESS_COOKIE = "ap2web_token"
REFRESH_COOKIE = "ap2web_refresh"
CSRF_COOKIE = "ap2web_csrf"

VALID_SAMESITE = {"lax", "strict", "none"}


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _as_int(value: str | None, default: int, lo: int | None = None, hi: int | None = None) -> int:
    try:
        v = int(value) if value is not None else default
    except (TypeError, ValueError):
        v = default
    if lo is not None and v < lo:
        v = lo
    if hi is not None and v > hi:
        v = hi
    return v


def _parse_origins(value: str | None, default: str) -> list[str]:
    raw = value if value is not None and str(value).strip() else default
    return [o.strip() for o in str(raw).split(",") if o.strip()]


class Settings:
    def __init__(self, environ: dict | None = None):
        env = environ if environ is not None else os.environ

        self.env: str = (env.get("AP2WEB_ENV") or "production").strip().lower()
        if self.env not in ("development", "production", "test"):
            self.env = "production"

        self.secret: str | None = (env.get("AP2WEB_SECRET") or "").strip() or None
        default_origins = (
            "http://localhost:5173,http://127.0.0.1:5173,https://app.theprostatereview.com"
            if self.env != "production"
            else ""
        )
        self.origins: list[str] = _parse_origins(env.get("AP2WEB_ORIGINS"), default_origins)

        self.enforce_roles: bool = _as_bool(
            env.get("AP2WEB_ENFORCE_ROLES"),
            default=(self.env == "production"),  # dev may opt out only explicitly
        )
        self.enable_worker: bool = _as_bool(env.get("AP2WEB_ENABLE_WORKER"), False)
        self.require_worker: bool = _as_bool(
            env.get("AP2WEB_REQUIRE_WORKER"), default=(self.env == "production"))
        self.worker_heartbeat_seconds: int = _as_int(
            env.get("AP2WEB_WORKER_HEARTBEAT_SECONDS"), 10, lo=2, hi=60)
        self.worker_lease_seconds: int = _as_int(
            env.get("AP2WEB_WORKER_LEASE_SECONDS"), 60, lo=10, hi=600)

        self.cookie_secure: bool = _as_bool(
            env.get("AP2WEB_COOKIE_SECURE"), default=(self.env == "production")
        )
        raw_samesite = (env.get("AP2WEB_COOKIE_SAMESITE") or "lax").strip().lower()
        self.cookie_samesite = raw_samesite if raw_samesite in VALID_SAMESITE else "lax"

        self.access_token_ttl_minutes: int = _as_int(
            env.get("AP2WEB_ACCESS_TOKEN_TTL_MINUTES"), 30, lo=1, hi=1440
        )
        self.refresh_token_ttl_days: int = _as_int(
            env.get("AP2WEB_REFRESH_TOKEN_TTL_DAYS"), 7, lo=1, hi=90
        )
        self.csrf_enabled: bool = _as_bool(env.get("AP2WEB_CSRF_ENABLED"), True)

        self.jwt_issuer: str = env.get("AP2WEB_JWT_ISSUER") or "ap2web"
        self.jwt_audience: str = env.get("AP2WEB_JWT_AUDIENCE") or "ap2web-api"
        # Clock skew tolerance in seconds (0 = strict). Enable only when
        # clock drift is a real problem in the deployment.
        self.jwt_clock_skew_seconds: int = _as_int(
            env.get("AP2WEB_JWT_CLOCK_SKEW_SECONDS"), 0, lo=0, hi=300
        )

        self.pbkdf2_iterations: int = _as_int(
            env.get("AP2WEB_PBKDF2_ITERATIONS"), 100_000, lo=10_000, hi=10_000_000
        )

        # Input validation limits
        self.username_min: int = _as_int(env.get("AP2WEB_USERNAME_MIN"), 3, lo=1, hi=20)
        self.username_max: int = _as_int(env.get("AP2WEB_USERNAME_MAX"), 32, lo=3, hi=64)
        self.password_min: int = _as_int(env.get("AP2WEB_PASSWORD_MIN"), 8, lo=6, hi=64)
        self.password_max: int = _as_int(env.get("AP2WEB_PASSWORD_MAX"), 128, lo=16, hi=512)
        self.max_body_bytes: int = _as_int(env.get("AP2WEB_MAX_BODY_BYTES"), 1024 * 1024, lo=4 * 1024, hi=64 * 1024 * 1024)

        # Rate limiting. Each value is a `limits` spec, e.g. "30/minute".
        self.rate_limit_enabled: bool = _as_bool(env.get("AP2WEB_RATE_LIMIT_ENABLED"), True)
        self.rate_limits: dict[str, str] = {
            "register": env.get("AP2WEB_RATE_REGISTER") or "10/minute",
            "login": env.get("AP2WEB_RATE_LOGIN") or "20/minute",
            "refresh": env.get("AP2WEB_RATE_REFRESH") or "30/minute",
            "prediction": env.get("AP2WEB_RATE_PREDICTION") or "60/minute",
            "fixture": env.get("AP2WEB_RATE_FIXTURE") or "60/minute",
            "sync": env.get("AP2WEB_RATE_SYNC") or "5/minute",
            "calibrate": env.get("AP2WEB_RATE_CALIBRATE") or "5/minute",
            "backtest": env.get("AP2WEB_RATE_BACKTEST") or "3/minute",
            "job_cancel": env.get("AP2WEB_RATE_JOB_CANCEL") or "30/minute",
            "admin": env.get("AP2WEB_RATE_ADMIN") or "20/minute",
        }

        self.audit_retention_days: int = _as_int(
            env.get("AP2WEB_AUDIT_RETENTION_DAYS"), 90, lo=1, hi=3650
        )

        # Rate-limit storage backend. `memory` is dev/test only: in production
        # limits must survive restarts and be shared across worker replicas.
        self.rate_limit_storage: str = (
            env.get("AP2WEB_RATE_LIMIT_STORAGE") or ("redis" if self.env == "production" else "memory")
        ).strip().lower()
        if self.rate_limit_storage not in ("memory", "redis"):
            self.rate_limit_storage = "memory"
        self.redis_url: str = (env.get("AP2WEB_REDIS_URL") or "").strip()

        # Comma-separated CIDRs considered "trusted proxies". The value of the
        # X-Forwarded-For header is only honored when the immediate TCP peer is
        # inside one of these ranges (per RFC 7239 best practice).
        self.trusted_proxy_cidrs: list[str] = [
            c.strip()
            for c in (env.get("AP2WEB_TRUSTED_PROXY_CIDRS") or "").split(",")
            if c.strip()
        ]

        self.cors_allow_methods = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
        self.cors_allow_headers = ["Content-Type", "Authorization", "X-CSRF-Token", "X-Request-ID"]
        self.cors_expose_headers = ["X-Request-ID"]
        self.cors_max_age = 600

        self.validate()

    # ── helpers ──────────────────────────────────────────────
    @property
    def production(self) -> bool:
        return self.env == "production"

    @property
    def access_token_ttl_seconds(self) -> int:
        return self.access_token_ttl_minutes * 60

    @property
    def refresh_token_ttl_seconds(self) -> int:
        return self.refresh_token_ttl_days * 24 * 3600

    def is_placeholder(self, secret: str | None) -> bool:
        return secret is not None and secret.strip() in _DEV_PLACEHOLDER_SECRETS

    def is_secret_weak(self, secret: str | None) -> bool:
        if not secret:
            return True
        s = secret.strip()
        if len(s) < 32:
            return True
        return self.is_placeholder(s)

    def validate(self) -> None:
        """Raise RuntimeError when configuration is unsafe for the environment."""
        if self.env == "production":
            if self.secret is None:
                raise RuntimeError("AP2WEB_SECRET is required in production.")
            if len(self.secret) < 32:
                raise RuntimeError("AP2WEB_SECRET must be at least 32 characters in production.")
            if self.is_placeholder(self.secret):
                raise RuntimeError(
                    "AP2WEB_SECRET is a known placeholder; forbidden in production. "
                    "Generate one with: python3 -c \"import secrets; print(secrets.token_hex(32))\""
                )
            if not self.enforce_roles:
                raise RuntimeError("AP2WEB_ENFORCE_ROLES=false is forbidden in production.")
            if not self.cookie_secure:
                raise RuntimeError("AP2WEB_COOKIE_SECURE=false is forbidden in production (must use HTTPS).")
            if not self.origins:
                raise RuntimeError("AP2WEB_ORIGINS must list explicit origins in production.")
            if "*" in self.origins:
                raise RuntimeError("Wildcard CORS origin is forbidden when credentials are enabled.")
            for o in self.origins:
                if o.startswith("*") or "://*" in o or "*." in o:
                    raise RuntimeError(f"Wildcard CORS origin not allowed in production: {o!r}")
            if self.rate_limit_storage == "memory":
                raise RuntimeError(
                    "AP2WEB_RATE_LIMIT_STORAGE=memory is forbidden in production: "
                    "limits must be shared across replicas and survive restarts. "
                    "Set AP2WEB_RATE_LIMIT_STORAGE=redis and AP2WEB_REDIS_URL."
                )
            if self.rate_limit_storage == "redis" and not self.redis_url:
                raise RuntimeError("AP2WEB_REDIS_URL is required when AP2WEB_RATE_LIMIT_STORAGE=redis.")
            if not self.require_worker:
                raise RuntimeError("AP2WEB_REQUIRE_WORKER=false is forbidden in production.")
        else:
            if self.origins and "*" in self.origins:
                raise RuntimeError("Wildcard CORS origin is never allowed (credentials are enabled).")
            if self.rate_limit_storage == "redis" and not self.redis_url:
                raise RuntimeError("AP2WEB_REDIS_URL is required when AP2WEB_RATE_LIMIT_STORAGE=redis.")


class _SettingsSingleton:
    _instance: Settings | None = None

    @classmethod
    def get(cls) -> Settings:
        if cls._instance is None:
            cls._instance = Settings()
        return cls._instance

    @classmethod
    def reset(cls, environ: dict | None = None) -> Settings:
        cls._instance = Settings(environ)
        return cls._instance


settings = _SettingsSingleton.get()
