"""pytest configuration.

Sets a deterministic, isolated test environment BEFORE any backend import so the
`config.settings` singleton and the `db` module pick up the right values. Each
pytest run gets its own temporary SQLite database under $TMPDIR that is removed
on interpreter exit — tests never touch the dev/production database, never share
usernames across files beyond their own fixtures, and never start background
workers.
"""
from __future__ import annotations

import atexit
import os
import shutil
import tempfile

import pytest

# Isolated per-run database (unique per process so parallel/overlapping runs
# cannot collide on a shared file).
_TEST_DIR = tempfile.mkdtemp(prefix="ap2web_pytest_")
_TEST_DB = os.path.join(_TEST_DIR, "test.db")


def _cleanup() -> None:
    shutil.rmtree(_TEST_DIR, ignore_errors=True)


atexit.register(_cleanup)

os.environ.setdefault("AP2WEB_ENV", "development")
os.environ.setdefault("AP2WEB_SECRET", "ci-test-secret-do-not-use-in-production-0123456789abcdef")
os.environ.setdefault("AP2WEB_DB_PATH", _TEST_DB)
# Keep authentication tests fast without weakening the production default.
# The minimum accepted value is still enforced by application configuration.
os.environ.setdefault("AP2WEB_PBKDF2_ITERATIONS", "10000")
# Background worker never runs inside the pytest process.
os.environ.setdefault("AP2WEB_ENABLE_WORKER", "false")
# Test-level security posture that mirrors production enforcement, but with
# cookie secure=false so httpx can round-trip cookies over http.
os.environ.setdefault("AP2WEB_ENFORCE_ROLES", "true")
os.environ.setdefault("AP2WEB_COOKIE_SECURE", "false")
os.environ.setdefault("AP2WEB_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
os.environ.setdefault("AP2WEB_CSRF_ENABLED", "true")
os.environ.setdefault("AP2WEB_RATE_LIMIT_ENABLED", "true")
# Rate limiting storage: tests use a fresh isolated in-memory store by default.
os.environ.setdefault("AP2WEB_RATE_LIMIT_STORAGE", "memory")


@pytest.fixture(scope="session", autouse=True)
def _db_ready():
    """Initialize the isolated schema before any test accesses the database.

    Direct unit tests that exercise ``backend.app.jobs`` / ``db`` internally
    (no TestClient lifespan) need a ready schema just like route tests get from
    the app startup hook.
    """
    from backend.app import db

    db.init_db()
    from backend.app import main, security

    security.prune_audit_log()
    main._app_started_ok = True
    yield
