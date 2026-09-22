"""Worker presence: registration, heartbeats and health."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from .. import db
from .registry import _lease_until

logger = logging.getLogger("ap2web.jobs")


def register_worker(worker_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    db.run_exec(
        "INSERT INTO workers(worker_id,started_at,last_heartbeat_at,status) VALUES(?,?,?,'online') "
        "ON CONFLICT(worker_id) DO UPDATE SET last_heartbeat_at=excluded.last_heartbeat_at,status='online'",
        (worker_id, now, now))


def heartbeat_worker(worker_id: str) -> None:
    db.run_exec("UPDATE workers SET last_heartbeat_at=?, status='online' WHERE worker_id=?",
                (datetime.now(timezone.utc).isoformat(), worker_id))


def stop_worker_record(worker_id: str) -> None:
    db.run_exec("UPDATE workers SET status='offline' WHERE worker_id=?", (worker_id,))


def worker_healthy(max_age_seconds: int) -> bool:
    cutoff = _lease_until(-max_age_seconds)
    rows = db.run_query(
        "SELECT 1 FROM workers WHERE status='online' AND last_heartbeat_at >= ? LIMIT 1",
        (cutoff,))
    return bool(rows)
