"""Password hashing (PBKDF2) and username/password policy."""
from __future__ import annotations

import hashlib
import hmac
import secrets

from .. import config
from .core import USERNAME_RE


_DUMMY_HASH: str | None = None
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
