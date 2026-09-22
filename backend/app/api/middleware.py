"""ASGI middleware: security headers, request-id and body-size enforcement."""
from __future__ import annotations

import logging
import time
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.datastructures import MutableHeaders

from .. import config, security

settings = config.settings
logger = logging.getLogger("ap2web")

_CSP_BASE = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "img-src 'self' data:; "
    "font-src https://fonts.gstatic.com; "
    "connect-src 'self' https://fonts.googleapis.com https://fonts.gstatic.com; "
    "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
)
if settings.production:
    _CSP = _CSP_BASE + "; upgrade-insecure-requests"
else:
    _CSP = _CSP_BASE

_SENSITIVE_PREFIXES = ("/api/login", "/api/logout", "/api/auth/", "/api/me")


class SecurityHeadersMiddleware:
    """Pure ASGI security middleware; avoids BaseHTTPMiddleware buffering."""

    def __init__(self, application):
        self.application = application

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.application(scope, receive, send)
            return

        request = Request(scope, receive)
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        request.state.request_id = rid
        start = time.time()
        content_length = request.headers.get("Content-Length")
        if content_length:
            try:
                if int(content_length) > settings.max_body_bytes:
                    response = JSONResponse(
                        status_code=413,
                        content=security.safe_error_body(
                            413, "Payload demasiado grande", request),
                        headers={"X-Request-ID": rid},
                    )
                    await response(scope, receive, send)
                    return
            except ValueError:
                pass

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
                headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
                headers["Content-Security-Policy"] = _CSP
                if settings.production:
                    headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
                headers["X-Request-ID"] = rid
                path = request.url.path
                is_api = path.startswith("/api/") or path == "/api"
                if is_api:
                    authed = bool(request.headers.get("Authorization")) or bool(
                        request.cookies.get(config.ACCESS_COOKIE))
                    sensitive = path.startswith(_SENSITIVE_PREFIXES) or request.method in (
                        "POST", "PUT", "PATCH", "DELETE")
                    if sensitive or authed:
                        headers["Cache-Control"] = "no-store"
                dur = (time.time() - start) * 1000
                if is_api and (dur > 500 or path in ("/api/sofascore/sync", "/api/learning/calibrate")):
                    logger.info("req rid=%s %s %s %s %.1fms", rid, request.method, path,
                                message["status"], dur)
            await send(message)

        await self.application(scope, receive, send_with_headers)
