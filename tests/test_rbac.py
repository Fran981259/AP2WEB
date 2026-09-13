import os
os.environ.setdefault("AP2WEB_SECRET", "ci-test-secret-do-not-use-in-production-0123456789abcdef")
os.environ.setdefault("AP2WEB_DB_PATH", "/tmp/ap2web_rbac_test2.db")
os.environ.setdefault("AP2WEB_ENV", "development")
os.environ.setdefault("AP2WEB_ENFORCE_ROLES", "true")
os.environ.setdefault("AP2WEB_COOKIE_SECURE", "false")
os.environ.setdefault("AP2WEB_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
# must set before import auth
from backend.app import db
from fastapi.testclient import TestClient
from backend.app.main import app

_cache: dict = {}


def _client():
    """Start the application lifespan for every TestClient instance."""
    return TestClient(app).__enter__()


def _setup():
    db.init_db()
    conn = db.get_conn()
    try:
        conn.execute("DELETE FROM jobs WHERE requested_by IN (SELECT id FROM users WHERE username IN ('rbac_user','rbac_op','rbac_admin'))")
        conn.execute("DELETE FROM users WHERE username IN ('rbac_user','rbac_op','rbac_admin')")
        conn.commit()
    finally:
        conn.close()
    _cache.clear()  # clear stale sessions from prior setups
    from backend.app.auth import create_user
    try:
        create_user("rbac_user", "pass1234", role="user")
    except Exception:
        pass
    try:
        create_user("rbac_op", "pass1234", role="operator")
    except Exception:
        pass
    try:
        create_user("rbac_admin", "pass1234", role="admin")
    except Exception:
        pass

def _login(u, p):
    key=(u,p)
    if key in _cache:
        return _cache[key]
    c = _client()
    r = c.post("/api/login", json={"username": u, "password": p})
    assert r.status_code == 200, r.text
    # handle cookie vs json: now login returns JSONResponse with cookie, but body still json
    try:
        tok=r.json()["token"]
    except Exception:
        tok=r.cookies.get("ap2web_token")
    _cache[key]=(tok,c)
    return tok,c

def test_user_cannot_sync():
    _setup()
    tok, c = _login("rbac_user", "pass1234")
    r = c.post("/api/sofascore/sync", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 403, f"user should 403 sync, got {r.status_code} {r.text}"

def test_operator_can_sync():
    _setup()
    tok, c = _login("rbac_op", "pass1234")
    r = c.post("/api/sofascore/sync", headers={"Authorization": f"Bearer {tok}"})
    # may be 200 job created or 409 already running
    assert r.status_code in (200, 409), r.text

def test_admin_can_calibrate():
    _setup()
    tok, c = _login("rbac_admin", "pass1234")
    r = c.post("/api/learning/calibrate", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code in (200, 409), r.text

def test_user_cannot_calibrate():
    _setup()
    tok, c = _login("rbac_user", "pass1234")
    r = c.post("/api/learning/calibrate", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 403

def test_invalid_token_401():
    _setup()
    c = _client()
    r = c.get("/api/leagues", headers={"Authorization": "Bearer invalid.token.here"})
    assert r.status_code == 401

def test_missing_sub_401():
    import jwt
    import time
    from backend.app import config
    tok = jwt.encode({"role": "user", "exp": int(time.time()) + 3600},
                     config.settings.secret, algorithm="HS256")
    c = _client()
    r = c.get("/api/leagues", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 401
