"""Phase 2 security tests — CSRF, CORS, headers, safe errors, payload cap."""
import pytest
from fastapi.testclient import TestClient

from backend.app import config, db
from backend.app.main import app


@pytest.fixture(scope="module")
def admin_client():
    with TestClient(app, raise_server_exceptions=True) as c:
        # seed an admin via direct role change
        try:
            create = c.post("/api/register", json={"username": "secadmin", "password": "supersecurepass"})
            if create.status_code not in (200, 409):
                raise AssertionError(create.status_code)
            db.run_exec("UPDATE users SET role='admin' WHERE username='secadmin'")
        except Exception:
            pass
        r = c.post("/api/login", json={"username": "secadmin", "password": "supersecurepass"})
        assert r.status_code == 200, r.text
        yield c


def test_csrf_blocks_mutation_without_header(admin_client):
    r = admin_client.post("/api/sofascore/sync", json={})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "CSRF_FAILED"


def test_csrf_blocks_wrong_token(admin_client):
    r = admin_client.post("/api/sofascore/sync", json={}, headers={"X-CSRF-Token": "deadbeef"})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "CSRF_FAILED"


def test_csrf_allows_valid_header(admin_client):
    csrf = admin_client.cookies.get(config.CSRF_COOKIE)
    assert csrf
    r = admin_client.post("/api/sofascore/sync", json={}, headers={"X-CSRF-Token": csrf})
    assert r.status_code in (200, 409), r.text
    assert r.json()["error"]["code"] != "CSRF_FAILED" if "error" in r.json() else True


def test_bearer_only_exempts_csrf():
    # fresh client (no session cookies) — Bearer-only must work without CSRF
    login_client = TestClient(app)
    login = login_client.post("/api/login", json={"username": "secadmin", "password": "supersecurepass"})
    assert login.status_code == 200, login.text
    token = login_client.cookies.get("ap2web_token")
    assert token
    bare = TestClient(app)  # separate client, no cookies set
    r = bare.post("/api/sofascore/sync", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code in (200, 409), r.text


def test_safe_methods_exempt_csrf(admin_client):
    r = admin_client.get("/api/me")
    assert r.status_code == 200


def test_security_headers(admin_client):
    r = admin_client.get("/api/me")
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-frame-options") == "DENY"
    assert "default-src 'self'" in r.headers.get("content-security-policy", "")
    assert r.headers.get("referrer-policy") is not None
    assert r.headers.get("permissions-policy") is not None
    assert r.headers.get("x-request-id") is not None


def test_authenticated_response_no_store(admin_client):
    r = admin_client.get("/api/me")
    assert "no-store" in r.headers.get("cache-control", "")


def test_error_shape_safe():
    c = TestClient(app)
    r = c.post("/api/login", json={})  # invalid body -> 400 validation
    assert r.status_code == 400
    body = r.json()
    assert "detail" in body
    assert "error" in body and "code" in body["error"] and "request_id" in body["error"]
    # no internal traceback/exception text
    assert "Traceback" not in r.text


def test_health_no_exception_leak():
    c = TestClient(app)
    r = c.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "Exception" not in r.text and "Traceback" not in r.text


def test_payload_too_large():
    c = TestClient(app)
    big = "a" * (config.settings.max_body_bytes + 1024)
    r = c.post("/api/login", json={"username": "big", "password": big})
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_cors_allows_configured_origin(admin_client):
    origin = "http://localhost:5173"
    r = admin_client.get("/api/me", headers={"Origin": origin})
    assert r.headers.get("access-control-allow-origin") == origin


def test_cors_rejects_disallowed_origin():
    c = TestClient(app)
    r = c.get("/api/me", headers={"Origin": "https://evil.example.com"})
    assert r.headers.get("access-control-allow-origin") != "https://evil.example.com"
