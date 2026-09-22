"""FastAPI dependencies: current user, RBAC gates, audit compat."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials

from .. import config, db, security
from ..columns import USERS
from .core import PERMISSIONS, VALID_ROLES, _bearer, logger
from .tokens import _check_session_live, _decode_access, _touch_session


def _extract_token(credentials: HTTPAuthorizationCredentials | None, request) -> str | None:
    if credentials and credentials.credentials:
        return credentials.credentials
    if request is not None:
        tok = request.cookies.get(config.ACCESS_COOKIE)
        if tok:
            return tok
    return None
def _resolve_user(request, credentials) -> dict:
    token = _extract_token(credentials, request)
    if not token:
        raise HTTPException(status_code=401, detail="Não autenticado")
    payload = _decode_access(token)
    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub.strip():
        raise HTTPException(status_code=401, detail="Token inválido")
    role_claim = payload.get("role")
    if role_claim is not None and role_claim.lower() not in VALID_ROLES:
        raise HTTPException(status_code=401, detail="Token inválido")
    sid = payload.get("sid")
    if sid is None or not _check_session_live(int(sid)):
        raise HTTPException(status_code=401, detail="Sessão inválida")

    rows = db.run_query(f"SELECT {USERS} FROM users WHERE username=?", (sub,))
    if not rows or dict(rows[0]).get("is_active") not in (None, 1, True):
        raise HTTPException(status_code=401, detail="Não autenticado")
    db_user = dict(rows[0])
    role = (db_user.get("role") or "user").lower()
    if role not in VALID_ROLES:
        role = "user"
    _touch_session(int(sid))
    return {
        "username": sub,
        "role": role,
        "payload": payload,
        "token": token,
        "user_id": int(db_user["id"]),
        "session_id": int(sid),
    }
def current_user(request: Request, credentials: HTTPAuthorizationCredentials = Depends(_bearer)) -> str:
    return _resolve_user(request, credentials)["username"]


def current_user_with_role(request: Request,
                           credentials: HTTPAuthorizationCredentials = Depends(_bearer)) -> dict:
    return _resolve_user(request, credentials)
def has_permission(role: str, perm: str) -> bool:
    role = (role or "user").lower()
    if role not in VALID_ROLES:
        return False
    if role == "admin":
        return True
    return perm in PERMISSIONS.get(role, set())


def is_enforcement_enabled() -> bool:
    """Production always enforces; development may opt out explicitly only."""
    return config.settings.enforce_roles
def require_permission(perm: str):
    """Dependency factory: ``Depends(require_permission("sync:data"))``."""
    def _checker(user: dict = Depends(current_user_with_role)) -> dict:
        role = (user.get("role") or "user").lower()
        if role not in VALID_ROLES:
            raise HTTPException(status_code=403, detail="Permissão negada")
        if not has_permission(role, perm):
            if not is_enforcement_enabled():
                logger.warning("RBAC soft-allow user=%s role=%s perm=%s env=%s (production would 403)",
                               user.get("username"), role, perm, config.settings.env)
                return user
            security.audit_event(
                None, action="authorization.rejected", success=False, error_code="FORBIDDEN",
                username=user.get("username"), role=role,
                metadata={"permission": perm, "resource_type": perm.split(":")[0]})
            raise HTTPException(status_code=403, detail="Permissão negada")
        return user
    return _checker
def require_role(*allowed_roles: str):
    """Legacy role dependency (admin always allowed). Kept for API compatibility."""
    allowed = {r.lower() for r in allowed_roles}

    def _checker(user: dict = Depends(current_user_with_role)) -> dict:
        role = (user.get("role") or "user").lower()
        if role == "admin" or role in allowed:
            return user
        if not is_enforcement_enabled():
            return user
        raise HTTPException(status_code=403, detail="Permissão negada")
    return _checker
def audit_log(action: str, username: str, details: str = "", *, request_id: str | None = None,
              success: bool = True, error: str | None = None, role: str | None = None,
              target: str | None = None) -> None:
    security.audit_event(
        None, action=action, success=success, error_code=error,
        username=username, role=role, resource_id=target,
        metadata={"details": details[:500], "request_id": request_id})
# Explicit env validation hook: config already validates at import, but keep a
# cheap re-check so that runtime .env edits cannot silence production rules.
if config.settings.production:
    if not config.settings.secret or config.settings.is_secret_weak(config.settings.secret):
        raise RuntimeError("AP2WEB_SECRET must be set to a strong value in production.")
    if not config.settings.enforce_roles:
        raise RuntimeError("AP2WEB_ENFORCE_ROLES=false is forbidden in production.")
    if not config.settings.cookie_secure:
        raise RuntimeError("AP2WEB_COOKIE_SECURE=false is forbidden in production.")
