"""DB user lookups, creation and first-admin bootstrap."""
from __future__ import annotations

from fastapi import HTTPException

from .. import config, db
from ..columns import USERS
from .core import VALID_ROLES, logger
from .password import (
    _normalize_username,
    _valid_password,
    _valid_username,
    hash_password,
)


def _db_user_by_name(username: str) -> dict | None:
    rows = db.run_query(f"SELECT {USERS} FROM users WHERE username=?", (_normalize_username(username),))
    return dict(rows[0]) if rows else None


def _db_user_case_insensitive(username: str) -> dict | None:
    rows = db.run_query(f"SELECT {USERS} FROM users WHERE LOWER(username)=LOWER(?)", (username,))
    return dict(rows[0]) if rows else None


def _user_role(username: str) -> str:
    row = _db_user_by_name(username)
    if row and row.get("role"):
        return str(row["role"]).lower()
    return "user"
def _ensure_role_column() -> None:
    try:
        db._ensure_user_cols()
    except Exception:
        pass


_ensure_role_column()
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
