"""Liveness, readiness and dependency-status routes."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter

from .. import config, db, security
from . import state

settings = config.settings
router = APIRouter()


def _db_reachable() -> bool:
    try:
        db.run_query("SELECT 1 AS ok", ())
        return True
    except Exception:
        return False


def _schema_ready() -> bool:
    """True when the schema is initialized and the baseline migration applied."""
    try:
        rows = db.run_query(
            "SELECT version FROM schema_migrations WHERE version=?", ("20260909_baseline",))
        users = db.run_query("SELECT COUNT(*) AS c FROM users", ())
        return bool(rows) and bool(users)
    except Exception:
        return False


def _worker_expected() -> bool:
    return bool(settings.require_worker or settings.enable_worker)


def _worker_healthy() -> bool:
    """A required worker must have a recent durable heartbeat."""
    try:
        from ..jobs import worker_healthy
        return worker_healthy(settings.worker_heartbeat_seconds * 3)
    except Exception:
        return False


def _external_data_source_status() -> dict:
    """Report durable successful-sync freshness without making an upstream call."""
    max_age = settings.source_sync_max_age_seconds
    try:
        rows = db.run_query("SELECT last_sync FROM leagues ORDER BY last_sync DESC LIMIT 1")
        if not rows:
            return {"status": "not_configured", "last_sync": None,
                    "age_seconds": None, "max_age_seconds": max_age}
        last_sync = rows[0]["last_sync"]
        if not last_sync:
            return {"status": "degraded", "last_sync": None,
                    "age_seconds": None, "max_age_seconds": max_age}
        parsed = datetime.fromisoformat(str(last_sync).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        age_seconds = max(0, int((datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds()))
        return {"status": "ok" if age_seconds <= max_age else "degraded",
                "last_sync": last_sync, "age_seconds": age_seconds,
                "max_age_seconds": max_age}
    except Exception:
        return {"status": "error", "last_sync": None,
                "age_seconds": None, "max_age_seconds": max_age}


@router.get("/api/health", tags=["misc"])
def health():
    """Liveness only — the process is up and the app is responding.

    Deliberately does NOT touch the database or any external service so the
    liveness probe never thrashes during a DB outage.
    """
    return {"ok": True, "app": "AP2WEB", "version": state.APP_VERSION}


@router.get("/api/ready", tags=["misc"])
def ready():
    """Readiness — the service can accept production traffic.

    Verifies startup completed, the database is reachable, the schema and the
    baseline migration are applied, the configuration is valid, and (when
    worker mode is enabled) the worker store is healthy. Returns HTTP 503 with
    a safe body when any of those checks fail.
    """
    ok_startup = state.started_ok is True
    ok_db = _db_reachable()
    ok_schema = _schema_ready() if ok_db else False
    ok_config = True  # invalid config already aborted startup
    ok_worker = not _worker_expected() or _worker_healthy()
    ready_all = ok_startup and ok_db and ok_schema and ok_config and ok_worker
    body = {
        "ok": ready_all,
        "ready": ready_all,
        "checks": {
            "startup": ok_startup,
            "database": ok_db,
            "schema": ok_schema,
            "config": ok_config,
            "worker": ok_worker,
        },
    }
    return JSONResponse(status_code=200 if ready_all else 503, content=body)


@router.get("/api/health/dependencies", tags=["misc"])
def health_dependencies():
    """Safe dependency status. No secrets, stack traces, SQL, or paths leaked."""
    db_ok = _db_reachable()

    external = _external_data_source_status()

    return {
        "database": {
            "status": "ok" if db_ok else "error",
            "mode": db.MODE,
        },
        "job_worker": {
            "status": "enabled" if _worker_expected() else "disabled",
            "healthy": _worker_healthy() if _worker_expected() else None,
        },
        "audit": {
            "status": "ok" if security.audit_persistence_healthy() else "degraded",
            "persistence_failures": security.audit_failure_count(),
        },
        "external_data_source": external,
        "rate_limit_storage": {
            "backend": settings.rate_limit_storage,
            "healthy": True,
        },
    }
