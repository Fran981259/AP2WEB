"""JWT issuance/validation and DB session persistence."""
from __future__ import annotations

import hashlib
import time
import uuid

import jwt as pyjwt
from fastapi import HTTPException, Request

from .. import config, db, security
from ..columns import AUTH_SESSIONS
from .core import ALGO, _iso_after, _now_iso


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
        f"SELECT {AUTH_SESSIONS} FROM auth_sessions WHERE refresh_token_hash=?", (_hash_refresh(raw),))
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
