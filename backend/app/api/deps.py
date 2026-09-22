"""Shared route dependencies and small helpers used by several routers."""
from __future__ import annotations

from fastapi import HTTPException, Request

from .. import db, security


def csrf_protect(request: Request) -> None:
    """CSRF dependency for state-changing endpoints (see security.csrf_protect)."""
    security.csrf_protect(request)


def audit(user: dict | None, action: str, request: Request | None = None, *,
          success: bool = True, error_code: str | None = None,
          resource_type: str | None = None, resource_id: str | int | None = None,
          metadata: dict | None = None) -> None:
    security.audit_event(
        request, action=action, success=success, error_code=error_code,
        username=(user or {}).get("username"), role=(user or {}).get("role"),
        resource_type=resource_type, resource_id=resource_id, metadata=metadata)


def clamp_limit(limit: int, hi: int = 100) -> int:
    try:
        value = int(limit)
    except (TypeError, ValueError):
        return 20
    return max(1, min(value, hi))


def user_id(username: str) -> int:
    row = db.run_query("SELECT id FROM users WHERE username=?", (username,))
    if not row:
        raise HTTPException(status_code=401, detail="Usuário não encontrado")
    return row[0]["id"]
