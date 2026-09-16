"""Autenticação hardening (Phase 2).

- PBKDF2-SHA256 com iterations configurável e documentado.
- JWT HS256 com iss/aud/iat/exp/jti/sid; alg fixo (nunca do token).
- Sessão em DB (auth_sessions): suporte a revogação + refresh rotation.
- Composição de cookies HttpOnly (access + refresh) com compat Bearer.
- Erros genéricos (sem enumeração de usuário) e policy de username/password.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import re
import secrets
import time
import uuid

import jwt as pyjwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import config, db, security

logger = logging.getLogger("ap2web.auth")

ALGO = "HS256"
_TOKEN_PREFIX = "Bearer "

VALID_ROLES = {"user", "operator", "admin"}
USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")

# Permissões por papel (deny-by-default; admin = "*").
PERMISSIONS: dict[str, set] = {
    "user": {
        "read:leagues", "read:teams", "read:matches", "read:predictions",
        "read:history", "read:jobs", "read:market", "read:risk",
    },
    "operator": {
        "read:leagues", "read:teams", "read:matches", "read:predictions",
        "read:history", "read:jobs", "read:market", "read:risk",
        "sync:data", "sync:league", "job:cancel",
    },
    "admin": {"*"},
}

_bearer = HTTPBearer(auto_error=False)

_DUMMY_HASH: str | None = None


# ── time helpers ─────────────────────────────────────────────
def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _iso_after(seconds: int) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + seconds))


# ── password hashing (PBKDF2-SHA256, configurable iterations) ─
def hash_password(password: str, salt: str | None = None) -> str:
    iterations = config.settings.pbkdf2_iterations
    salt_hex = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                 salt_hex.encode("ascii"), iterations).hex()
    return f"{iterations}${salt_hex}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        parts = stored.split("$")
        if len(parts) == 3:
            iterations, salt, digest = int(parts[0]), parts[1], parts[2]
        elif len(parts) == 2:
            # legacy: salt$digest (default iterations)
            iterations, salt, digest = 100_000, parts[0], parts[1]
        else:
            return False
        if not (10_000 <= iterations <= 10_000_000) or not salt or not digest:
            return False
    except (ValueError, IndexError):
        return False
    check = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                salt.encode("ascii"), iterations).hex()
    return hmac.compare_digest(check, digest)


def _dummy_hash() -> str:
    """Equalizes login timing for unknown usernames."""
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = hash_password("timing-equalization-dummy-password")
    return _DUMMY_HASH


# ── username / password validation ───────────────────────────
def _valid_username(username: str) -> bool:
    u = (username or "").strip()
    return (
        config.settings.username_min <= len(u) <= config.settings.username_max
        and bool(USERNAME_RE.match(u))
    )


def _valid_password(password: str) -> bool:
    if not password or password.strip() == "":
        return False
    return config.settings.password_min <= len(password) <= config.settings.password_max


def _normalize_username(username: str) -> str:
    return (username or "").strip().lower()


def _db_user_by_name(username: str) -> dict | None:
    rows = db.run_query("SELECT * FROM users WHERE username=?", (_normalize_username(username),))
    return dict(rows[0]) if rows else None


def _db_user_case_insensitive(username: str) -> dict | None:
    rows = db.run_query("SELECT * FROM users WHERE LOWER(username)=LOWER(?)", (username,))
    return dict(rows[0]) if rows else None


def _user_role(username: str) -> str:
    row = _db_user_by_name(username)
    if row and row.get("role"):
        return str(row["role"]).lower()
    return "user"


# ── schema helpers ───────────────────────────────────────────
def _ensure_role_column() -> None:
    try:
        db._ensure_user_cols()
    except Exception:
        pass


_ensure_role_column()


# ── JWT ──────────────────────────────────────────────────────
def _issue_access_token(username: str, role: str, sid: int) -> str:
    now = int(time.time())
    payload = {
        "sub": username,
        "role": role,
        "iss": config.settings.jwt_issuer,
        "aud": config.settings.jwt_audience,
        "iat": now,
        "exp": now + config.settings.access_token_ttl_seconds,
        "jti": uuid.uuid4().hex,
        "sid": int(sid),
    }
    return pyjwt.encode(payload, config.settings.secret, algorithm=ALGO)


def _decode_access(token: str) -> dict:
    """Strict decode: signature, alg whitelist, iss/aud/exp. Never trusts token 'alg'."""
    try:
        payload = pyjwt.decode(
            token,
            config.settings.secret,
            algorithms=[ALGO],
            issuer=config.settings.jwt_issuer,
            audience=config.settings.jwt_audience,
            leeway=config.settings.jwt_clock_skew_seconds,
            options={
                "require": ["sub", "exp", "iss", "aud", "jti", "sid", "iat"],
            },
        )
        return payload
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Sessão expirada")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")


# ── session persistence ──────────────────────────────────────
def _hash_refresh(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _create_session_row(user_id: int, username: str, request: Request | None,
                        refresh_raw: str, ttl_seconds: int,
                        family: str | None = None) -> tuple[int, str]:
    family = family or uuid.uuid4().hex
    ip = security.client_ip(request) if request else None
    ua = (request.headers.get("User-Agent") or None) if request else None
    sid = db.run_exec(
        "INSERT INTO auth_sessions(user_id,access_jti,refresh_token_hash,family_id,expires_at,"
        "ip_address,user_agent,created_at) VALUES(?,?,?,?,?,?,?,datetime('now'))",
        (user_id, "", _hash_refresh(refresh_raw), family, _iso_after(ttl_seconds), ip, ua))
    return int(sid), family


def _check_session_live(sid: int) -> bool:
    try:
        rows = db.run_query("SELECT revoked_at, expires_at FROM auth_sessions WHERE id=?", (sid,))
    except Exception:
        return False
    if not rows:
        return False
    row = dict(rows[0])
    if row.get("revoked_at"):
        return False
    if not row.get("expires_at"):
        return False
    return row["expires_at"] >= _now_iso()


def _session_by_refresh(raw: str) -> dict | None:
    rows = db.run_query(
        "SELECT * FROM auth_sessions WHERE refresh_token_hash=?", (_hash_refresh(raw),))
    return dict(rows[0]) if rows else None


def _revoke_session(sid: int, reason: str) -> None:
    db.run_exec(
        "UPDATE auth_sessions SET revoked_at=datetime('now'), revoked_reason=? WHERE id=?",
        (reason, sid))


def _revoke_family(family_id: str, reason: str) -> None:
    db.run_exec(
        "UPDATE auth_sessions SET revoked_at=datetime('now'), revoked_reason=? WHERE family_id=?",
        (reason, family_id))


def _touch_session(sid: int) -> None:
    try:
        db.run_exec("UPDATE auth_sessions SET last_used_at=datetime('now') WHERE id=?", (sid,))
    except Exception:
        pass


# ── create / authenticate ────────────────────────────────────
def create_user(username: str, password: str, role: str = "user") -> int:
    username = _normalize_username(username)
    if not _valid_username(username):
        raise HTTPException(
            status_code=400,
            detail=f"Nome de usuário deve ter {config.settings.username_min}-{config.settings.username_max} "
                   f"caracteres e apenas A-Z, 0-9, . _ -")
    if not _valid_password(password):
        raise HTTPException(
            status_code=400,
            detail=f"Senha deve ter entre {config.settings.password_min} e {config.settings.password_max} "
                   f"caracteres e não pode ser apenas espaços")
    if role not in VALID_ROLES:
        role = "user"
    _ensure_role_column()
    if _db_user_case_insensitive(username) is not None:
        raise HTTPException(status_code=409, detail="Usuário já existe")
    try:
        return db.run_exec(
            "INSERT INTO users(username,password_hash,role,is_active) VALUES(?,?,?,1)",
            (username, hash_password(password), role))
    except Exception as e:
        msg = str(e).lower()
        if "unique" in msg or "duplicate" in msg or "conflict" in msg:
            raise HTTPException(status_code=409, detail="Usuário já existe")
        logger.warning("create_user failed (infra): %s", type(e).__name__)
        raise HTTPException(status_code=500, detail="Erro interno ao criar usuário")


def bootstrap_admin(username: str | None, password: str | None) -> bool:
    """Create or promote the explicitly configured first administrator.

    This is intentionally a no-op unless both values are configured and the
    database has no active administrator. It makes first deployment
    reproducible without shipping a default credential or requiring direct SQL
    access to the production database.
    """
    if not username and not password:
        return False
    if not username or not password:
        raise RuntimeError("Bootstrap administrator credentials are incomplete.")

    admins = db.run_query(
        "SELECT 1 FROM users WHERE role='admin' AND is_active=1 LIMIT 1"
    )
    if admins:
        return False

    normalized = _normalize_username(username)
    existing = _db_user_case_insensitive(normalized)
    if existing is not None:
        # The operator explicitly named this account and there is no other
        # active admin. Promoting it is preferable to creating a second user.
        db.run_exec("UPDATE users SET role='admin', is_active=1 WHERE id=?", (existing["id"],))
        return True

    try:
        create_user(normalized, password, role="admin")
        return True
    except HTTPException as exc:
        # Multiple API replicas may bootstrap at the same time. The unique
        # username index elects one winner; the loser confirms the result.
        if exc.status_code != 409:
            raise
        admins = db.run_query(
            "SELECT 1 FROM users WHERE role='admin' AND is_active=1 LIMIT 1"
        )
        if admins:
            return False
        raise


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


# ── refresh rotation ─────────────────────────────────────────
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

    rows = db.run_query("SELECT * FROM users WHERE id=?", (sess["user_id"],))
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


# ── logout ───────────────────────────────────────────────────
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
                    sess_rows = db.run_query("SELECT * FROM auth_sessions WHERE id=?", (sid,))
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


# ── dependency-level auth ────────────────────────────────────
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

    rows = db.run_query("SELECT * FROM users WHERE username=?", (sub,))
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


# ── RBAC helpers ─────────────────────────────────────────────
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


# ── legacy audit_log (compat with Phase 1 callers) ───────────
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
