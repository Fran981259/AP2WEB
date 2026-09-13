"""Phase 2 security tests — auth, session, tokens, config validation."""
import time

import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient

from backend.app import config, db
from backend.app.main import app

# ---------------------------------------------------------------------------
# Config validation (uses Settings(environ=...) directly — no DB needed)
# ---------------------------------------------------------------------------

def test_production_rejects_short_secret():
    with pytest.raises(RuntimeError, match="at least 32 characters"):
        config.Settings({
            "AP2WEB_ENV": "production",
            "AP2WEB_SECRET": "short",
            "AP2WEB_ORIGINS": "https://ok.example.com",
            "AP2WEB_ENFORCE_ROLES": "true",
            "AP2WEB_COOKIE_SECURE": "true",
        })


def test_production_rejects_placeholder_secret():
    with pytest.raises(RuntimeError, match="placeholder"):
        config.Settings({
            "AP2WEB_ENV": "production",
            "AP2WEB_SECRET": "dev-secret-change-me-please-use-env-var-0123456789abcdef",
            "AP2WEB_ORIGINS": "https://ok.example.com",
            "AP2WEB_ENFORCE_ROLES": "true",
            "AP2WEB_COOKIE_SECURE": "true",
        })


def test_production_rejects_enforce_false():
    with pytest.raises(RuntimeError, match="AP2WEB_ENFORCE_ROLES=false"):
        config.Settings({
            "AP2WEB_ENV": "production",
            "AP2WEB_SECRET": "ci-test-secret-do-not-use-in-production-0123456789abcdef",
            "AP2WEB_ORIGINS": "https://ok.example.com",
            "AP2WEB_ENFORCE_ROLES": "false",
            "AP2WEB_COOKIE_SECURE": "true",
        })


def test_production_rejects_cookie_secure_false():
    with pytest.raises(RuntimeError, match="AP2WEB_COOKIE_SECURE=false"):
        config.Settings({
            "AP2WEB_ENV": "production",
            "AP2WEB_SECRET": "ci-test-secret-do-not-use-in-production-0123456789abcdef",
            "AP2WEB_ORIGINS": "https://ok.example.com",
            "AP2WEB_ENFORCE_ROLES": "true",
            "AP2WEB_COOKIE_SECURE": "false",
        })


def test_production_rejects_empty_origins():
    with pytest.raises(RuntimeError, match="explicit origins"):
        config.Settings({
            "AP2WEB_ENV": "production",
            "AP2WEB_SECRET": "ci-test-secret-do-not-use-in-production-0123456789abcdef",
            "AP2WEB_ORIGINS": "",
            "AP2WEB_ENFORCE_ROLES": "true",
            "AP2WEB_COOKIE_SECURE": "true",
        })


def test_production_rejects_wildcard_origin():
    with pytest.raises(RuntimeError, match="Wildcard"):
        config.Settings({
            "AP2WEB_ENV": "production",
            "AP2WEB_SECRET": "ci-test-secret-do-not-use-in-production-0123456789abcdef",
            "AP2WEB_ORIGINS": "https://*.example.com",
            "AP2WEB_ENFORCE_ROLES": "true",
            "AP2WEB_COOKIE_SECURE": "true",
        })


def test_production_accepts_valid_config():
    s = config.Settings({
        "AP2WEB_ENV": "production",
        "AP2WEB_SECRET": "ci-test-secret-do-not-use-in-production-0123456789abcdef",
        "AP2WEB_ORIGINS": "https://ok.example.com",
        "AP2WEB_ENFORCE_ROLES": "true",
        "AP2WEB_COOKIE_SECURE": "true",
        "AP2WEB_RATE_LIMIT_STORAGE": "redis",
        "AP2WEB_REDIS_URL": "redis://localhost:6379/0",
    })
    assert s.production is True
    assert s.access_token_ttl_seconds > 0
    assert s.refresh_token_ttl_seconds > 0


def test_production_rejects_memory_ratelimit():
    import pytest

    with pytest.raises(RuntimeError):
        config.Settings({
            "AP2WEB_ENV": "production",
            "AP2WEB_SECRET": "ci-test-secret-do-not-use-in-production-0123456789abcdef",
            "AP2WEB_ORIGINS": "https://ok.example.com",
            "AP2WEB_RATE_LIMIT_STORAGE": "memory",
        })


def test_production_rejects_redis_without_url():
    import pytest

    with pytest.raises(RuntimeError):
        config.Settings({
            "AP2WEB_ENV": "production",
            "AP2WEB_SECRET": "ci-test-secret-do-not-use-in-production-0123456789abcdef",
            "AP2WEB_ORIGINS": "https://ok.example.com",
            "AP2WEB_RATE_LIMIT_STORAGE": "redis",
        })


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Auth flow (requires DB)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    # The session fixture already creates a unique database for this pytest run.
    # Removing it here invalidates the schema used by every later module.
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


@pytest.fixture(scope="module")
def user_session(client):
    """Register + login and return the login data dict."""
    r = client.post("/api/register", json={"username": "secuser2", "password": "supersecurepass"})
    assert r.status_code == 200
    r = client.post("/api/login", json={"username": "secuser2", "password": "supersecurepass"})
    assert r.status_code == 200
    return r.json()


def test_login_sets_cookies(client, user_session):
    cookies = dict(client.cookies)
    assert "ap2web_token" in cookies
    assert "ap2web_refresh" in cookies
    assert "ap2web_csrf" in cookies
    assert len(cookies["ap2web_token"]) > 20
    assert "token" not in user_session
    assert "refresh_token" not in user_session
    assert "csrf_token" not in user_session


def test_username_identity_is_case_insensitive():
    with TestClient(app) as isolated:
        created = isolated.post("/api/register", json={"username": "CaseUser", "password": "supersecurepass"})
        assert created.status_code == 200, created.text
        duplicate = isolated.post("/api/register", json={"username": "caseuser", "password": "supersecurepass"})
        assert duplicate.status_code == 409
        logged_in = isolated.post("/api/login", json={"username": "CASEUSER", "password": "supersecurepass"})
        assert logged_in.status_code == 200, logged_in.text
        assert logged_in.json()["username"] == "caseuser"


def test_me_returns_username(client, user_session):
    r = client.get("/api/me")
    assert r.status_code == 200
    assert r.json()["username"] == "secuser2"
    assert r.json()["role"] == "user"


def test_jwt_claims_present(client, user_session):
    # Tokens are HttpOnly cookies and must not be exposed in the JSON body.
    assert "token" not in user_session
    assert "refresh_token" not in user_session
    token = client.cookies.get("ap2web_token")
    assert token
    payload = pyjwt.decode(token, config.settings.secret, algorithms=["HS256"],
                           issuer=config.settings.jwt_issuer,
                           audience=config.settings.jwt_audience,
                           options={"require": ["sub", "exp", "iss", "aud", "jti", "sid", "iat"]})
    assert payload["sub"] == "secuser2"
    assert payload["role"] == "user"
    assert payload["iss"] == config.settings.jwt_issuer
    assert payload["aud"] == config.settings.jwt_audience
    assert "jti" in payload
    assert "sid" in payload
    assert payload["exp"] > time.time()


def test_refresh_rotation(client):
    # Login fresh
    r = client.post("/api/register", json={"username": "refresher", "password": "supersecurepass"})
    if r.status_code not in (200, 409):
        raise AssertionError(r.status_code)
    r = client.post("/api/login", json={"username": "refresher", "password": "supersecurepass"})
    assert r.status_code == 200
    old_refresh = client.cookies.get("ap2web_refresh")
    old_access = client.cookies.get("ap2web_token")
    assert old_refresh and old_access

    # First refresh succeeds (rotation)
    csrf = client.cookies.get("ap2web_csrf")
    r = client.post("/api/auth/refresh", json={}, headers={"X-CSRF-Token": csrf})
    assert r.status_code == 200
    new_refresh = client.cookies.get("ap2web_refresh")
    assert new_refresh != old_refresh
    assert client.cookies.get("ap2web_token") != old_access  # different access token
    assert "token" not in r.json()
    assert "refresh_token" not in r.json()
    assert "csrf_token" not in r.json()

    # Second refresh with old (now-rotated) refresh token must fail
    # (directly via DB lookup — client already has new cookie, so we test the function)
    from backend.app.auth import refresh_session
    from fastapi import HTTPException
    with pytest.raises(HTTPException, match="Sessão inválida"):
        refresh_session(old_refresh)


def test_logout_revokes_family(client):
    r = client.post("/api/register", json={"username": "logoutuser", "password": "supersecurepass"})
    if r.status_code not in (200, 409):
        raise AssertionError(r.status_code)
    r = client.post("/api/login", json={"username": "logoutuser", "password": "supersecurepass"})
    assert r.status_code == 200
    csrf = client.cookies.get("ap2web_csrf")
    # logout
    r = client.post("/api/logout", headers={"X-CSRF-Token": csrf})
    assert r.status_code == 200
    # me must now 401
    r = client.get("/api/me")
    assert r.status_code == 401


def test_inactive_user_rejected(client):
    # Create user, then deactivate
    from backend.app.auth import create_user
    try:
        create_user("inactiveuser", "supersecurepass")
    except Exception:
        pass
    # deactivate directly in DB
    db.run_exec("UPDATE users SET is_active=0 WHERE username='inactiveuser'")
    r = client.post("/api/login", json={"username": "inactiveuser", "password": "supersecurepass"})
    assert r.status_code == 401
    assert "Credenciais inválidas" in r.json().get("detail", "")


def test_generic_error_message(client):
    r = client.post("/api/login", json={"username": "nonexistent_user_xyz", "password": "anything"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Credenciais inválidas"


def test_username_policy(client):
    # too short
    r = client.post("/api/register", json={"username": "ab", "password": "supersecurepass"})
    assert r.status_code == 400
    # invalid chars
    r = client.post("/api/register", json={"username": "us er!", "password": "supersecurepass"})
    assert r.status_code == 400
    # whitespace only
    r = client.post("/api/register", json={"username": "   ", "password": "supersecurepass"})
    assert r.status_code == 400
