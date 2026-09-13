"""Phase 2 security tests — rate limiting (runtime toggleable)."""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.ratelimit import rate_limiter


@pytest.fixture(scope="module", autouse=True)
def protect_other_tests():
    """Ensure counters are cleared after this module so later tests are unaffected."""
    rate_limiter.set_enabled(True)
    rate_limiter.reset()
    yield
    rate_limiter.reset()


@pytest.fixture(scope="module")
def client():
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def test_register_rate_limit(client):
    rate_limiter.reset()
    rate_limiter.set_enabled(True)
    statuses = []
    for i in range(12):
        r = _register(client, f"ratelimit_user_{i}")
        statuses.append(r.status_code)
    # limit is 10/minute
    assert statuses[:10] == [200] * 10, statuses
    assert statuses[10] == 429, statuses
    assert statuses[11] == 429, statuses


def test_login_rate_limit(client):
    rate_limiter.reset()
    rate_limiter.set_enabled(True)
    statuses = []
    for i in range(22):
        r = client.post("/api/login",
                        json={"username": f"nonexistent_{i}", "password": "wrongpass"})
        statuses.append(r.status_code)
    # limit is 20/minute
    assert statuses[:20] == [401] * 20, statuses
    assert statuses[20] == 429, statuses
    assert statuses[21] == 429, statuses


def test_429_error_shape(client):
    rate_limiter.reset()
    rate_limiter.set_enabled(True)
    statuses = [_register(client, f"ratelimit_shape_{i}").status_code for i in range(16)]
    assert 429 in statuses
    r = _register(client, "ratelimit_shape_final")
    assert r.status_code == 429
    body = r.json()
    assert body["error"]["code"] == "RATE_LIMITED"
    assert "Retry-After" in r.headers


def test_rate_limit_can_be_disabled(client):
    rate_limiter.reset()
    rate_limiter.set_enabled(False)
    # limit is 10/minute but enforcement is off; 14 are allowed
    statuses = [_register(client, f"ratelimit_off_{i}").status_code for i in range(14)]
    assert statuses[:10] == [200] * 10, statuses
    assert len([s for s in statuses if s == 429]) == 0, statuses


def _register(client, username: str):
    return client.post("/api/register", json={"username": username, "password": "supersecurepass"})