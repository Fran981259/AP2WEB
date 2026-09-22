"""Versioned API surface: ``/api/v1/*`` aliases with response envelope.

Legacy ``/api/*`` routes keep their exact contract for existing clients.
Every legacy ``/api/*`` route is ALSO served under ``/api/v1/*`` with the
canonical envelope ``{"data", "message", "statusCode"}`` (AGENTS.md).

Aliases share the endpoint function AND the route dependencies of the legacy
route, so CSRF + rate-limit protection is identical on both surfaces.
"""
from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.datastructures import MutableHeaders

V1_PREFIX = "/api/v1"


def register_v1_aliases(app: FastAPI, routers) -> list[str]:
    """Mirror every legacy ``/api/*`` route under ``/api/v1/*``.

    Iterates the routers' own route lists (concrete ``APIRoute`` objects):
    recent FastAPI defers ``include_router`` flattening via ``_IncludedRouter``
    placeholders, so ``app.routes`` is not reliable at import time.
    Must run after ``include_router`` calls (and before the SPA catch-all,
    which would otherwise shadow the new paths). Returns created paths.
    """
    created = []
    seen = set()
    for router in routers:
        for route in getattr(router, "routes", []):
            if not isinstance(route, APIRoute):
                continue
            path = route.path
            if not path.startswith("/api/") or path.startswith(V1_PREFIX + "/"):
                continue
            key = (path, tuple(sorted(route.methods or ["GET"])))
            if key in seen:
                continue
            seen.add(key)
            v1_path = V1_PREFIX + path[len("/api"):]
            app.add_api_route(
                v1_path,
                route.endpoint,
                methods=sorted(route.methods or ["GET"]),
                dependencies=list(route.dependencies or []),
                status_code=route.status_code,
                name=f"v1_{route.name}" if route.name else None,
            )
            created.append(v1_path)
    return created


class V1EnvelopeMiddleware:
    """Pure ASGI middleware: wrap ``/api/v1/*`` JSON bodies in the envelope.

    ``{"data": <legacy body>, "message": "ok"|"error",
      "statusCode": <http status>}``. Non-JSON responses pass through
    untouched; the HTTP status code is never altered.
    """

    def __init__(self, application):
        self.application = application

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope.get("path", "").startswith(V1_PREFIX + "/"):
            await self.application(scope, receive, send)
            return
        captured: dict = {}
        chunks: list[bytes] = []

        async def capture(message):
            if message["type"] == "http.response.start":
                captured["status"] = message["status"]
                captured["headers"] = list(message.get("headers", []))
            elif message["type"] == "http.response.body":
                chunks.append(message.get("body", b""))
                if message.get("more_body"):
                    return
                await self._send_enveloped(send, captured, b"".join(chunks))
            else:
                # Background tasks, pathsend, debug …: forward untouched.
                await send(message)

        await self.application(scope, receive, capture)

    async def _send_enveloped(self, send, captured: dict, raw: bytes) -> None:
        status = captured.get("status", 500)
        headers = MutableHeaders(raw=captured.get("headers", []))
        body = raw
        if headers.get("content-type", "").startswith("application/json"):
            try:
                data = json.loads(raw.decode("utf-8")) if raw else None
            except (ValueError, UnicodeDecodeError):
                data = None
            if data is not None or not raw:
                envelope = {
                    "data": data,
                    "message": "ok" if status < 400 else "error",
                    "statusCode": status,
                }
                body = json.dumps(envelope).encode("utf-8")
        headers["content-length"] = str(len(body))
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": headers.raw,
        })
        await send({"type": "http.response.body", "body": body, "more_body": False})
