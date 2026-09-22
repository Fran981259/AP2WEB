"""Administration routes: role changes, user deactivation and audit reads."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Path, Request
from fastapi.routing import APIRouter

from .. import config, db, security
from ..auth import require_permission
from ..ratelimit import rate_limit
from .deps import audit, clamp_limit, csrf_protect
from .models import RoleChangeBody

settings = config.settings
router = APIRouter()


@router.post("/api/admin/users/{user_id}/role", tags=["admin"])
def admin_set_role(user_id: int = Path(gt=0), body: RoleChangeBody | None = None,
                   request: Request = None,  # FastAPI injects; kept for audit
                   admin: dict = Depends(require_permission("manage:users")),
                   _: None = Depends(csrf_protect),
                   __: None = Depends(rate_limit("admin"))):
    if body is None:
        raise HTTPException(status_code=400, detail="Payload vazio — informe o novo papel")
    if int(admin.get("user_id") or 0) == user_id:
        raise HTTPException(status_code=400, detail="Não é possível alterar o próprio papel")
    rows = db.run_query("SELECT id, username FROM users WHERE id=?", (user_id,))
    if not rows:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    db.run_exec("UPDATE users SET role=? WHERE id=?", (body.role, user_id))
    audit(admin, "admin.role_change", request, success=True,
          resource_type="user", resource_id=user_id,
          metadata={"target": rows[0]["username"], "new_role": body.role})
    return {"ok": True, "user_id": user_id, "username": rows[0]["username"], "role": body.role}


@router.delete("/api/admin/users/{user_id}", tags=["admin"])
def admin_delete_user(user_id: int = Path(gt=0), request: Request = None,
                      admin: dict = Depends(require_permission("manage:users")),
                      _: None = Depends(csrf_protect),
                      __: None = Depends(rate_limit("admin"))):
    if int(admin.get("user_id") or 0) == user_id:
        raise HTTPException(status_code=400, detail="Não é possível excluir a si mesmo")
    rows = db.run_query("SELECT id, username FROM users WHERE id=?", (user_id,))
    if not rows:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    db.run_exec("UPDATE users SET is_active=0 WHERE id=?", (user_id,))
    # revoke all of the user's sessions
    db.run_exec("UPDATE auth_sessions SET revoked_at=datetime('now'), revoked_reason='user_deleted' "
                "WHERE user_id=? AND revoked_at IS NULL", (user_id,))
    audit(admin, "admin.user_delete", request, success=True,
          resource_type="user", resource_id=user_id, metadata={"target": rows[0]["username"]})
    return {"ok": True, "deleted_user_id": user_id, "username": rows[0]["username"]}


@router.get("/api/admin/audit", tags=["admin"])
def admin_audit(limit: int = 100, action: str | None = None,
                admin: dict = Depends(require_permission("manage:system"))):
    items = security.admin_audit_records(clamp_limit(limit, 500), action)
    return {"items": items, "count": len(items),
            "retention_days": settings.audit_retention_days}
