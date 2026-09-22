"""Native-client bearer authentication contract tests."""
from fastapi.testclient import TestClient

from backend.app.main import app


def test_mobile_login_returns_bearer_credentials():
    with TestClient(app) as client:
        created = client.post(
            "/api/register",
            json={"username": "mobile_user", "password": "supersecurepass"},
        )
        assert created.status_code in (200, 409)

        response = client.post(
            "/api/v1/mobile/auth/login",
            json={"username": "mobile_user", "password": "supersecurepass"},
        )

    assert response.status_code == 200, response.text
    payload = response.json()["data"]
    assert payload["token_type"] == "bearer"
    assert payload["access_token"]
    assert payload["refresh_token"]
    assert payload["user"]["username"] == "mobile_user"
    assert "csrf_token" not in payload


def test_mobile_refresh_rotates_refresh_token():
    with TestClient(app) as client:
        login = client.post(
            "/api/v1/mobile/auth/login",
            json={"username": "mobile_user", "password": "supersecurepass"},
        )
        refresh = login.json()["data"]["refresh_token"]
        response = client.post(
            "/api/v1/mobile/auth/refresh",
            json={"refresh_token": refresh},
        )

    assert response.status_code == 200, response.text
    payload = response.json()["data"]
    assert payload["access_token"]
    assert payload["refresh_token"] != refresh


def test_mobile_logout_accepts_bearer_token():
    with TestClient(app) as client:
        login = client.post(
            "/api/v1/mobile/auth/login",
            json={"username": "mobile_user", "password": "supersecurepass"},
        )
        token = login.json()["data"]["access_token"]
        response = client.post(
            "/api/v1/mobile/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["ok"] is True
