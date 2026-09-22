"""Safe error formatting: stable codes, no internal leakage."""
from __future__ import annotations

from fastapi import Request

from .core import request_id


_ERROR_CODES = {
    400: "VALIDATION_ERROR",
    401: "AUTHENTICATION_REQUIRED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    429: "RATE_LIMITED",
    500: "INTERNAL_ERROR",
    503: "SERVICE_UNAVAILABLE",
}
def error_code_for(status_code: int, detail: str = "") -> str:
    if detail.upper().startswith("INVALID_CSRF"):
        return "CSRF_FAILED"
    return _ERROR_CODES.get(int(status_code), "INTERNAL_ERROR")
def safe_error_body(status_code: int, message: str, request: Request | None = None,
                    *, detail: str | None = None) -> dict:
    rid = request_id(request) if request else None
    err = {
        "code": error_code_for(status_code, message),
        "message": message,
        "request_id": rid,
    }
    body = {"detail": detail if detail is not None else message, "error": err}
    return body
