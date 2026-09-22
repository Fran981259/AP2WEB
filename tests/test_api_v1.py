"""Contract tests for /api/v1/* aliases: envelope shape, legacy parity."""
import uuid

from fastapi.testclient import TestClient

from backend.app.main import app


def _paths():
    return sorted(app.openapi()["paths"])


def test_v1_aliases_cover_every_legacy_api_route():
    paths = _paths()
    legacy = [p for p in paths if p.startswith("/api/") and not p.startswith("/api/v1/")]
    assert legacy, "no legacy routes found"
    for path in legacy:
        assert f"/api/v1{path[len('/api'):]}" in paths, f"missing v1 alias for {path}"


def test_v1_health_returns_envelope_matching_legacy_body():
    with TestClient(app) as c:
        legacy = c.get("/api/health")
        v1 = c.get("/api/v1/health")
    assert legacy.status_code == 200
    assert v1.status_code == 200
    body = v1.json()
    assert body["data"] == legacy.json()
    assert body["message"] == "ok"
    assert body["statusCode"] == 200
    assert "data" not in legacy.json()


def test_v1_mutating_register_flows_through_alias():
    username = f"v1user_{uuid.uuid4().hex[:8]}"
    with TestClient(app) as c:
        r = c.post("/api/v1/register", json={"username": username, "password": "supersecurepass"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["statusCode"] == 200
        assert body["message"] == "ok"
        assert body["data"] == {"ok": True, "message": "Usuário criado"}
        r = c.post("/api/v1/login", json={"username": username, "password": "supersecurepass"})
        assert r.status_code == 200, r.text
        assert r.json()["data"]["username"] == username


def test_v1_error_responses_keep_status_and_envelope():
    with TestClient(app) as c:
        r = c.get("/api/v1/me")
        legacy = c.get("/api/me")
    assert r.status_code == 401 == legacy.status_code
    body = r.json()
    assert body["statusCode"] == 401
    assert body["message"] == "error"
    # request_id is unique per request; everything else must match legacy.
    data, legacy_data = dict(body["data"]), legacy.json()
    data.get("error", {}).pop("request_id", None)
    legacy_data.get("error", {}).pop("request_id", None)
    assert data == legacy_data
