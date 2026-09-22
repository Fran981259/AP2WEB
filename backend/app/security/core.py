"""Security core: logger, error type, request ids and client IP."""
from __future__ import annotations

import logging
import threading

from fastapi import Request

from .. import config


logger = logging.getLogger("ap2web.security")
_audit_lock = threading.Lock()
class SecurityError(Exception):
    """Internal marker for failed security checks (translated to a status by handlers)."""

    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)
def request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or "unknown"


def _trusted_proxy(peer_ip: str) -> bool:
    """True when ``peer_ip`` is inside one of the configured trusted CIDRs."""
    if not config.settings.trusted_proxy_cidrs:
        return False
    try:
        import ipaddress
        return any(
            ipaddress.ip_address(peer_ip) in ipaddress.ip_network(cidr, strict=False)
            for cidr in config.settings.trusted_proxy_cidrs
        )
    except ValueError:
        return False
def client_ip(request: Request) -> str:
    """Best-effort client IP.

    - Explicit overrides (set by middleware later) win.
    - ``X-Forwarded-For`` is ONLY honored when the immediate TCP peer is inside
      a configured trusted proxy CIDR (``AP2WEB_TRUSTED_PROXY_CIDRS``). Without
      an explicit allow-list, unverifiable spoofable headers are ignored — the
      raw socket peer is used instead. This closes the header-spoofing hole
      (the peer is trusted to set the header by whoever deployed the trusted
      proxy, not by any remote client).
    """
    if request.state.__dict__.get("client_ip"):
        return request.state.client_ip
    peer = request.client.host if request.client else "unknown"
    if _trusted_proxy(peer):
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return peer
