"""Job registry: CRUD, claims, leases and completion over the jobs table."""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from .. import db
from ..columns import JOBS

logger = logging.getLogger("ap2web.jobs")


ALLOWED_TYPES = {"sync_all","sync_league","sync_odds","calibrate_all","calibrate_league","backtest","health"}
class _JobCancelled(Exception):
    """Internal control-flow marker: the worker must stop a cancelled job."""


def _lease_until(seconds: int) -> str:
    return (datetime.now(timezone.utc) + __import__("datetime").timedelta(seconds=seconds)).isoformat()
def _idempotency_key(job_type: str, league_id: Optional[int], params: dict | None) -> str:
    raw = json.dumps({"t":job_type,"l":league_id,"p":params or {}}, sort_keys=True)
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return hashlib.sha256((raw+"|"+date).encode()).hexdigest()[:32]
def create_job(job_type: str, requested_by: int, league_id: int | None = None,
               parameters: dict | None = None, idempotency_key: str | None = None) -> dict:
    if job_type not in ALLOWED_TYPES:
        raise ValueError(f"unknown job_type {job_type}")
    params_json = json.dumps(parameters or {}, ensure_ascii=False)
    if not idempotency_key:
        idempotency_key = _idempotency_key(job_type, league_id, parameters)
    # duplicate prevention: if pending/running with same key, return existing
    rows = db.run_query(f"SELECT {JOBS} FROM jobs WHERE idempotency_key=? AND status IN ('pending','running')", (idempotency_key,))
    if rows:
        logger.info("duplicate job prevented key=%s existing=%s", idempotency_key, rows[0]["id"])
        return dict(rows[0])
    # single active calibration/promotion guard
    if job_type in ("calibrate_all","promotion"):
        active = db.run_query(f"SELECT {JOBS} FROM jobs WHERE job_type=? AND status IN ('pending','running')", (job_type,))
        if active:
            raise RuntimeError(f"Job {job_type} already active id={active[0]['id']}")
    # also for sync_league same league
    if job_type == "sync_league" and league_id is not None:
        active = db.run_query(f"SELECT {JOBS} FROM jobs WHERE job_type='sync_league' AND league_id=? AND status IN ('pending','running')", (league_id,))
        if active:
            raise RuntimeError(f"Sync for league {league_id} already active id={active[0]['id']}")
    # sync_all ingests every configured league, so it cannot overlap a targeted sync.
    if job_type == "sync_all":
        active = db.run_query(
            f"SELECT {JOBS} FROM jobs WHERE job_type='sync_league' AND status='running' LIMIT 1")
        if active:
            raise RuntimeError(f"Targeted sync already active id={active[0]['id']}")
    if job_type == "sync_league":
        active = db.run_query(
            f"SELECT {JOBS} FROM jobs WHERE job_type='sync_all' AND status='running' LIMIT 1")
        if active:
            raise RuntimeError(f"Full sync already active id={active[0]['id']}")
    try:
        jid = db.run_exec(
            "INSERT INTO jobs(job_type,status,requested_by,league_id,parameters,idempotency_key,created_at,updated_at) VALUES(?,?,?,?,?,?,datetime('now'),datetime('now'))",
            (job_type, "pending", requested_by, league_id, params_json, idempotency_key))
    except Exception as e:
        msg = str(e).lower()
        if "unique" in msg or "duplicate" in msg:
            rows = db.run_query(f"SELECT {JOBS} FROM jobs WHERE idempotency_key=?", (idempotency_key,))
            if rows:
                return dict(rows[0])
        raise
    row = db.run_query(f"SELECT {JOBS} FROM jobs WHERE id=?", (jid,))
    logger.info("job created id=%s type=%s by=%s league=%s key=%s", jid, job_type, requested_by, league_id, idempotency_key)
    return dict(row[0]) if row else {"id": jid, "job_type": job_type, "status":"pending"}
def get_job(job_id: int) -> dict | None:
    rows = db.run_query(f"SELECT {JOBS} FROM jobs WHERE id=?", (job_id,))
    return dict(rows[0]) if rows else None
def list_jobs(user_id: int | None = None, limit: int = 50, job_type: str | None = None) -> list[dict]:
    limit = max(1, min(int(limit), 100))
    q = f"SELECT {JOBS} FROM jobs"
    conds: list[str] = []
    params: list = []
    if user_id is not None:
        conds.append("requested_by=?")
        params.append(user_id)
    if job_type:
        conds.append("job_type=?")
        params.append(job_type)
    if conds:
        q += " WHERE " + " AND ".join(conds)
    q += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    return [dict(r) for r in db.run_query(q, tuple(params))]
def cancel_job(job_id: int, user: dict) -> dict:
    job = get_job(job_id)
    if not job:
        raise LookupError("job not found")
    role = (user.get("role") or "user").lower()
    username = user.get("username")
    is_owner = (job["requested_by"] == user.get("user_id")
                or (isinstance(username, str)
                    and job["requested_by"] == _user_id_by_name(username)))
    if role not in ("admin", "operator") and not is_owner:
        raise PermissionError("not allowed to cancel")
    if job["status"] not in ("pending", "running"):
        return job
    # mark cancelled if pending, or attempt cancel if running (worker should check)
    db.run_exec("UPDATE jobs SET status='cancelled', idempotency_key=NULL, cancelled_at=datetime('now'), updated_at=datetime('now') WHERE id=? AND status IN ('pending','running')", (job_id,))
    logger.info("job cancelled id=%s by %s", job_id, user.get("username"))
    return get_job(job_id) or job

def _user_id_by_name(username: str) -> int | None:
    rows = db.run_query("SELECT id FROM users WHERE username=?", (username,))
    return rows[0]["id"] if rows else None
def claim_job(job_id: int, worker_id: str, lease_seconds: int = 60) -> bool:
    """Try to claim pending -> running with optimistic locking (PG safe)."""
    job = get_job(job_id)
    if not job:
        return False
    if job["job_type"] in ("sync_all", "sync_league"):
        with db.transaction():
            # PostgreSQL needs a shared lock because these claims update different job rows.
            if db.MODE == "postgres":
                db.run_query("SELECT pg_advisory_xact_lock(?)", (821539,))
            job = get_job(job_id)
            if not job or job["status"] != "pending":
                return False
            other_type = "sync_league" if job["job_type"] == "sync_all" else "sync_all"
            active = db.run_query(
                "SELECT 1 FROM jobs WHERE job_type=? AND status='running' LIMIT 1", (other_type,))
            if active:
                return False
            return db.run_exec("UPDATE jobs SET status='running', started_at=datetime('now'), worker_id=?, lease_expires_at=?, attempt_count=attempt_count+1, updated_at=datetime('now') WHERE id=? AND status='pending'", (worker_id, _lease_until(lease_seconds), job_id)) == 1
    return db.run_exec("UPDATE jobs SET status='running', started_at=datetime('now'), worker_id=?, lease_expires_at=?, attempt_count=attempt_count+1, updated_at=datetime('now') WHERE id=? AND status='pending'", (worker_id, _lease_until(lease_seconds), job_id)) == 1


def renew_job_lease(job_id: int, worker_id: str, lease_seconds: int = 60) -> bool:
    return db.run_exec("UPDATE jobs SET lease_expires_at=?, updated_at=datetime('now') WHERE id=? AND status='running' AND worker_id=?", ( _lease_until(lease_seconds), job_id, worker_id)) == 1
def complete_job(job_id: int, result: dict | None = None, progress: float = 1.0):
    res_json = json.dumps(result or {}, ensure_ascii=False)
    db.run_exec("UPDATE jobs SET status='completed', idempotency_key=NULL, progress=?, result=?, finished_at=datetime('now'), updated_at=datetime('now') WHERE id=? AND status='running'", (progress, res_json, job_id))
    logger.info("job completed id=%s", job_id)

def fail_job(job_id: int, error: str, attempt: int | None = None, result: dict | None = None):
    err = error[:2000]
    res_json = json.dumps(result or {}, ensure_ascii=False)
    db.run_exec("UPDATE jobs SET status='failed', idempotency_key=NULL, error_message=?, result=?, finished_at=datetime('now'), updated_at=datetime('now') WHERE id=? AND status='running'", (err, res_json, job_id))
def update_progress(job_id: int, progress: float, detail: str | None = None,
                    worker_id: str | None = None, lease_seconds: int = 60):
    # Keep progress bounded; detail is logged until a dedicated progress payload exists.
    bounded = max(0.0, min(float(progress), 1.0))
    if detail:
        logger.debug("job progress id=%s detail=%s", job_id, detail[:200])
    if worker_id:
        renew_job_lease(job_id, worker_id, lease_seconds)
    db.run_exec("UPDATE jobs SET progress=?, updated_at=datetime('now') WHERE id=? AND status='running'", (bounded, job_id))
def recover_expired_jobs() -> int:
    """Manual recovery ONLY after operators have stopped all workers.

    A process startup does not prove another worker died. Automatic recovery
    requires leases/heartbeats and must not call this administrative helper.
    """
    now = datetime.now(timezone.utc).isoformat()
    rows = db.run_query(
        f"SELECT {JOBS} FROM jobs WHERE status='running' AND lease_expires_at < ?", (now,))
    for r in rows:
        try:
            db.run_exec("UPDATE jobs SET status='failed', idempotency_key=NULL, error_message='recovered: worker lease expired', finished_at=datetime('now'), updated_at=datetime('now') WHERE id=? AND status='running' AND lease_expires_at < ?", (r["id"], now))
            logger.warning("recovered stale job id=%s type=%s", r["id"], r["job_type"])
        except Exception:
            logger.exception("recover job %s failed", r["id"])
    return len(rows)
def job_metrics() -> dict:
    rows = db.run_query("SELECT status, COUNT(*) c FROM jobs GROUP BY status")
    return {r["status"]: r["c"] for r in rows}
