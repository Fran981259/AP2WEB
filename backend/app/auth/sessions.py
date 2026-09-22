"""Login, refresh rotation and logout."""
from __future__ import annotations

import secrets

from fastapi import HTTPException, Request

from .. import config, db, security
from ..columns import AUTH_SESSIONS, USERS
from .core import VALID_ROLES, _now_iso
from .password import _dummy_hash, _normalize_username, verify_password
from .tokens import (
    _create_session_row,
    _decode_access,
    _issue_access_token,
    _revoke_family,
    _revoke_session,
    _session_by_refresh,
    _touch_session,
)
from .users import _db_user_by_name


def authenticate(username: str, password: str, request: Request | None = None,
                 session_ttl: int | None = None) -> dict:
    """Login. Returns tokens + csrf. Generic 401 (no username oracle)."""
    username = _normalize_username(username)
    row = _db_user_by_name(username)
    if not row or not verify_password(password, row["password_hash"]):
        if not row:
            # equalize timing for unknown usernames
            verify_password(password, _dummy_hash())
        security.audit_event(
            request, action="login.failure", success=False, error_code="AUTH_FAILED",
            metadata={"username": username})
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    if row.get("is_active") not in (None, 1, True):
        verify_password(password, _dummy_hash())
        security.audit_event(
            request, action="login.failure", success=False, error_code="AUTH_FAILED",
            metadata={"username": username})
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    role = (row.get("role") or "user").lower()
    if role not in VALID_ROLES:
        role = "user"
    ttl = session_ttl or config.settings.refresh_token_ttl_seconds
    refresh_raw = secrets.token_urlsafe(48)
    sid, family = _create_session_row(int(row["id"]), username, request, refresh_raw, ttl)
    csrf = security.generate_csrf_token()
    token = _issue_access_token(username, role, sid)
    _touch_session(sid)
    security.audit_event(
        request, action="login.success", success=True, username=username, role=role,
        user_id=int(row["id"]), metadata={"sid": sid})
    return {
        "token": token,
        "username": username,
        "role": role,
        "refresh_token": refresh_raw,
        "csrf_token": csrf,
        "session_id": sid,
        "expires_in": config.settings.access_token_ttl_seconds,
    }
def refresh_session(refresh_raw: str, request: Request | None = None) -> dict:
    """Rotate refresh token. Reuse of a revoked token kills the session family."""
    sess = _session_by_refresh(refresh_raw)
    if not sess:
        security.audit_event(request, action="auth.refresh_failure", success=False,
                             error_code="REFRESH_INVALID")
        raise HTTPException(status_code=401, detail="Sessão inválida")
    if sess.get("revoked_at"):
        _revoke_family(sess["family_id"], "reuse_detected")
        security.audit_event(request, action="auth.refresh_reuse", success=False,
                             error_code="REFRESH_REUSE", metadata={"family": sess["family_id"]})
        raise HTTPException(status_code=401, detail="Sessão inválida")
    if sess.get("expires_at") and sess["expires_at"] < _now_iso():
        security.audit_event(request, action="auth.refresh_failure", success=False,
                             error_code="REFRESH_EXPIRED", metadata={"sid": sess["id"]})
        raise HTTPException(status_code=401, detail="Sessão expirada")

    rows = db.run_query(f"SELECT {USERS} FROM users WHERE id=?", (sess["user_id"],))
    if not rows or dict(rows[0]).get("is_active") not in (None, 1, True):
        _revoke_family(sess["family_id"], "user_inactive")
        raise HTTPException(status_code=401, detail="Sessão inválida")
    user = dict(rows[0])
    role = (user.get("role") or "user").lower()
    if role not in VALID_ROLES:
        role = "user"

    _revoke_session(int(sess["id"]), "rotated")
    refresh_raw_new = secrets.token_urlsafe(48)
    sid, family = _create_session_row(int(sess["user_id"]), user["username"], request,
                                      refresh_raw_new, config.settings.refresh_token_ttl_seconds,
                                      family=sess["family_id"])
    csrf = security.generate_csrf_token()
    token = _issue_access_token(user["username"], role, sid)
    _touch_session(sid)
    security.audit_event(request, action="auth.refresh", success=True, username=user["username"],
                         role=role, user_id=int(user["id"]), metadata={"sid": sid, "rotated_from": sess["id"]})
    return {
        "token": token,
        "username": user["username"],
        "role": role,
        "refresh_token": refresh_raw_new,
        "csrf_token": csrf,
        "session_id": sid,
        "expires_in": config.settings.access_token_ttl_seconds,
    }
def logout_session(request: Request) -> dict:
    """Revoke the current session family. Works even with an expired access token."""
    revoked: list[int] = []
    refresh_raw = request.cookies.get(config.REFRESH_COOKIE)
    if refresh_raw:
        sess = _session_by_refresh(refresh_raw)
        if sess:
            family = sess.get("family_id")
            _revoke_session(int(sess["id"]), "logout")
            revoked.append(int(sess["id"]))
            if family:
                sibling = db.run_query(
                    "SELECT id FROM auth_sessions WHERE family_id=? AND revoked_at IS NULL", (family,))
                for s in sibling:
                    _revoke_session(int(s["id"]), "logout")
                    revoked.append(int(s["id"]))
    else:
        # legacy path: revoke by access token sid if possible
        token = request.cookies.get(config.ACCESS_COOKIE)
        auth = request.headers.get("Authorization", "")
        if token or auth.lower().startswith("bearer "):
            raw = token or auth[7:].strip()
            try:
                payload = _decode_access(raw)
                sid = payload.get("sid")
                if sid is not None:
                    sess_rows = db.run_query(f"SELECT {AUTH_SESSIONS} FROM auth_sessions WHERE id=?", (sid,))
                    if sess_rows:
                        row = dict(sess_rows[0])
                        if row.get("family_id"):
                            _revoke_family(row["family_id"], "logout")
                        else:
                            _revoke_session(int(sid), "logout")
                        revoked.append(int(sid))
            except HTTPException:
                pass  # expired token — nothing else to do
    security.audit_event(request, action="logout", success=True,
                         metadata={"revoked_ids": revoked or None})
    return {"revoked_sessions": len(revoked)}
