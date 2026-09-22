"""Phase 2 security tests — PBKDF2 password hashing."""


def test_password_hash_new_format():
    from backend.app.auth import hash_password, verify_password
    h = hash_password("testpass123")
    parts = h.split("$")
    assert len(parts) == 3, "new hash should be iterations$salt$digest"
    assert int(parts[0]) >= 10_000
    assert verify_password("testpass123", h) is True
    assert verify_password("wrongpass", h) is False


def test_password_hash_legacy_compat():
    import hashlib
    import secrets
    from backend.app.auth import verify_password
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", b"testpass123", salt.encode(), 100_000).hex()
    legacy_hash = f"{salt}${digest}"
    assert verify_password("testpass123", legacy_hash) is True
    assert verify_password("wrongpass", legacy_hash) is False
