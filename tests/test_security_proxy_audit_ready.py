"""Phase 3 security tests — proxy/IP handling, audit reliability, readiness.

Covers the gaps closed in Steps 9-12 of the hardening plan:
- X-Forwarded-For is only trusted from allow-listed proxies;
- audit persistence health + recursive redaction of sensitive metadata;
- /api/ready + /api/health/dependencies service contracts (503 on failure);
- cookie attributes and refresh/logout CSRF enforcement.
"""
from __future__ import annotations


import pytest
from fastapi.testclient import TestClient

from backend.app import config, db, jobs, security
from backend.app.main import app


@pytest.fixture(scope="module")
def user_client():
    with TestClient(app, raise_server_exceptions=True) as c:
        r = c.post("/api/register", json={"username": "phase3user", "password": "supersecurepass"})
        assert r.status_code in (200, 409), r.text
        r = c.post("/api/login", json={"username": "phase3user", "password": "supersecurepass"})
        assert r.status_code == 200, r.text
        yield c


# ---------------------------------------------------------------------------
# Trusted proxy → client IP
# ---------------------------------------------------------------------------

class _FakeRequest:
    def __init__(self, peer: str, forwarded: str | None):
        class _client:
            host = peer
        self.client = _client()
        self.state = type("S", (), {"__dict__": {}})()
        self.headers = {"X-Forwarded-For": forwarded} if forwarded else {}


def _with_proxy_cidrs(cidrs, fn):
    old = config.settings.trusted_proxy_cidrs
    try:
        config.settings.trusted_proxy_cidrs = cidrs
        return fn()
    finally:
        config.settings.trusted_proxy_cidrs = old


def test_xff_ignored_without_trusted_proxy():
    r = _FakeRequest(peer="203.0.113.9", forwarded="6.6.6.6")
    assert security.client_ip(r) == "203.0.113.9"


def test_xff_honored_from_trusted_proxy():
    r = _FakeRequest(peer="10.0.0.5", forwarded="8.8.4.4, 10.0.0.5")
    ip = _with_proxy_cidrs(["10.0.0.0/8"], lambda: security.client_ip(r))
    assert ip == "8.8.4.4"


def test_xff_still_ignored_from_untrusted_peer():
    r = _FakeRequest(peer="203.0.113.9", forwarded="6.6.6.6")
    ip = _with_proxy_cidrs(["10.0.0.0/8"], lambda: security.client_ip(r))
    assert ip == "203.0.113.9"


# ---------------------------------------------------------------------------
# Audit reliability + redaction
# ---------------------------------------------------------------------------

def test_audit_health_starts_clean():
    assert security.audit_failure_count() == 0
    assert security.audit_persistence_healthy() is True


def test_audit_redacts_nested_sensitive_metadata():
    security.audit_event(
        action="test.redaction", username="phase3user",
        metadata={
            "ok": True,
            "nested": {"password": "supersecret", "token": "abc123", "keep": "visible"},
            "list": [{"api_key": "k-123"}],
        },
    )
    rows = db.run_query(
        "SELECT metadata FROM audit_events WHERE action='test.redaction' ORDER BY id DESC LIMIT 1")
    assert rows, "audit row must exist"
    stored = (rows[0]["metadata"] or "")
    assert "supersecret" not in stored
    assert "abc123" not in stored
    assert "k-123" not in stored
    assert "visible" in stored
    assert "sha256:" in stored


# ---------------------------------------------------------------------------
# Readiness / dependencies
# ---------------------------------------------------------------------------

def test_ready_ok_after_startup():
    with TestClient(app) as c:
        r = c.get("/api/ready")
        assert r.status_code == 200
        body = r.json()
        assert body["ready"] is True
        assert body["checks"]["startup"] is True
        assert body["checks"]["database"] is True


def test_ready_503_when_db_down(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("db down")
    monkeypatch.setattr(db, "run_query", _boom)
    c = TestClient(app)
    r = c.get("/api/ready")
    assert r.status_code == 503
    assert r.json()["ready"] is False


def test_ready_requires_recent_worker_when_configured():
    old = config.settings.require_worker
    try:
        config.settings.require_worker = True
        with TestClient(app) as c:
            assert c.get("/api/ready").status_code == 503
            jobs.register_worker("ready-test-worker")
            response = c.get("/api/ready")
            assert response.status_code == 200
            assert response.json()["checks"]["worker"] is True
    finally:
        jobs.stop_worker_record("ready-test-worker")
        config.settings.require_worker = old


def test_health_dependencies_shape():
    c = TestClient(app)
    r = c.get("/api/health/dependencies")
    assert r.status_code == 200
    body = r.json()
    assert body["database"]["mode"] in ("sqlite", "postgres")
    assert "job_worker" in body
    assert "audit" in body
    assert body["rate_limit_storage"]["backend"] in ("memory", "redis")
    assert "last_sync" in body["external_data_source"]
    # fresh DB seeds leagues without sync -> "degraded", never "error" (sqlite Row has no .get)
    assert body["external_data_source"]["status"] in ("ok", "degraded", "not_configured")
    assert body["external_data_source"]["status"] != "error"


# ---------------------------------------------------------------------------
# Cookie attributes + refresh/logout CSRF
# ---------------------------------------------------------------------------

def test_session_cookies_have_safety_attributes():
    c = TestClient(app)
    c.post("/api/register", json={"username": "cookieman", "password": "supersecurepass"})
    resp = c.post("/api/login", json={"username": "cookieman", "password": "supersecurepass"})
    assert resp.status_code == 200, resp.text
    set_cookies = resp.headers.get_list("set-cookie")
    names = {part.split("=", 1)[0].strip() for part in set_cookies}
    assert {"ap2web_token", "ap2web_refresh", "ap2web_csrf"} <= names
    for raw in set_cookies:
        name = raw.split("=", 1)[0].strip()
        # Session/auth cookies must be HttpOnly; the CSRF cookie intentionally
        # stays readable by JS (double-submit pattern).
        if name in ("ap2web_token", "ap2web_refresh"):
            assert "HttpOnly" in raw
        assert "SameSite=" in raw
        assert "Path=" in raw


def test_refresh_requires_csrf_header():
    c = TestClient(app)
    c.post("/api/register", json={"username": "refreshuser", "password": "supersecurepass"})
    c.post("/api/login", json={"username": "refreshuser", "password": "supersecurepass"})
    r = c.post("/api/auth/refresh")
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "CSRF_FAILED"


def test_refresh_works_with_csrf_header():
    c = TestClient(app)
    c.post("/api/register", json={"username": "refreshuser", "password": "supersecurepass"})
    c.post("/api/login", json={"username": "refreshuser", "password": "supersecurepass"})
    csrf = c.cookies.get(config.CSRF_COOKIE)
    assert csrf
    r = c.post("/api/auth/refresh", json={}, headers={"X-CSRF-Token": csrf})
    assert r.status_code == 200, r.text


def test_logout_requires_csrf_header():
    c = TestClient(app)
    c.post("/api/register", json={"username": "logoutuser", "password": "supersecurepass"})
    c.post("/api/login", json={"username": "logoutuser", "password": "supersecurepass"})
    r = c.post("/api/logout")
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "CSRF_FAILED"
