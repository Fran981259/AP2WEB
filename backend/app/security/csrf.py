"""CSRF double-submit cookie protection for state-changing endpoints."""
from __future__ import annotations

import hmac
import uuid

from fastapi import HTTPException, Request

from .. import config
from .audit import audit_event


def generate_csrf_token() -> str:
    return uuid.uuid4().hex + uuid.uuid4().hex
def csrf_protect(request: Request) -> None:
    """Dependency for state-changing (POST/PUT/PATCH/DELETE) endpoints.

    - Safe methods (GET/HEAD/OPTIONS) are never checked.
    - Requests authenticated by a non-cookie credential (``Authorization:
      Bearer ...``) are exempt: the header is not auto-sent by browsers, so a
      CSRF attacker cannot provide it. (DRF-equivalent rule.)
    - Remaining cookie sessions must present X-CSRF-Token matching the
      double-submit cookie, compared in constant time. Tokens are NEVER
      accepted from query parameters.
    """
    if not config.settings.csrf_enabled:
        return
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    auth = request.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer ") and auth[7:].strip():
        # Non-cookie credential present → no CSRF needed.
        return
    has_session = bool(
        request.cookies.get(config.ACCESS_COOKIE) or request.cookies.get(config.REFRESH_COOKIE)
    )
    if not has_session:
        # Machine-to-machine / cookie-less clients keep working without CSRF.
        return
    supplied = request.headers.get("X-CSRF-Token", "")
    cookie_val = request.cookies.get(config.CSRF_COOKIE, "")
    if not supplied or not cookie_val or not hmac.compare_digest(supplied, cookie_val):
        audit_event(
            request, action="csrf.rejected", success=False, error_code="CSRF_FAILED",
            metadata={"origin": request.headers.get("Origin", ""), "method": request.method},
        )
        raise HTTPException(status_code=403, detail="INVALID_CSRF")
