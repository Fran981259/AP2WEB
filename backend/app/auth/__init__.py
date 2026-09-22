"""Autenticação hardening (Phase 2).

- PBKDF2-SHA256 com iterations configurável e documentado.
- JWT HS256 com iss/aud/iat/exp/jti/sid; alg fixo (nunca do token).
- Sessão em DB (auth_sessions): suporte a revogação + refresh rotation.
- Composição de cookies HttpOnly (access + refresh) com compat Bearer.
- Erros genéricos (sem enumeração de usuário) e policy de username/password.

Decomposto em submódulos temáticos; este pacote reexporta o API pública do
antigo módulo ``auth``.
"""
from __future__ import annotations

from .core import PERMISSIONS, VALID_ROLES
from .dependencies import (
    audit_log,
    current_user,
    current_user_with_role,
    has_permission,
    is_enforcement_enabled,
    require_permission,
    require_role,
)
from .password import hash_password, verify_password
from .sessions import authenticate, logout_session, refresh_session
from .tokens import _decode_access, _issue_access_token
from .users import _db_user_by_name, bootstrap_admin, create_user

__all__ = [
    "PERMISSIONS",
    "VALID_ROLES",
    "audit_log",
    "authenticate",
    "bootstrap_admin",
    "create_user",
    "current_user",
    "current_user_with_role",
    "has_permission",
    "is_enforcement_enabled",
    "logout_session",
    "refresh_session",
    "require_permission",
    "require_role",
    "hash_password",
    "verify_password",
    "_db_user_by_name",
    "_decode_access",
    "_issue_access_token",
]
