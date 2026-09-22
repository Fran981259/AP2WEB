"""Worker loop: polling, thread lifecycle and start/stop."""
from __future__ import annotations

import logging
import threading
import time
import uuid

from .. import db
from ..columns import JOBS
from .runner import _run_one
from .workers import heartbeat_worker, register_worker, stop_worker_record

logger = logging.getLogger("ap2web.jobs")


_worker_thread: threading.Thread | None = None
_worker_stop = threading.Event()
def run_worker_loop(stop_event: threading.Event | None = None, worker_id: str | None = None,
                    heartbeat_seconds: int = 10, lease_seconds: int = 60) -> None:
    """Polling loop over the persistent job store.

    Run either in-process (dev opt-in via ``AP2WEB_ENABLE_WORKER=true``) or as
    the main thread of the standalone worker process (``python -m
    backend.app.worker``) — the only production-supported execution model.
    """
    if stop_event is None:
        stop_event = _worker_stop
    worker_id = worker_id or f"worker-{uuid.uuid4().hex[:12]}"
    register_worker(worker_id)
    next_heartbeat = 0.0
    while not stop_event.is_set():
        try:
            if time.monotonic() >= next_heartbeat:
                heartbeat_worker(worker_id)
                next_heartbeat = time.monotonic() + heartbeat_seconds
            pending = db.run_query(f"SELECT {JOBS} FROM jobs WHERE status='pending' ORDER BY id LIMIT 5")
            for job in pending:
                j = dict(job)
                _run_one(j, worker_id, lease_seconds)
                if stop_event.is_set():
                    break
        except Exception:
            logger.exception("worker loop error")
        stop_event.wait(timeout=min(2.0, heartbeat_seconds))
    stop_worker_record(worker_id)


def _worker_loop():
    run_worker_loop(_worker_stop)

def start_worker():
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        return
    _worker_stop.clear()
    _worker_thread = threading.Thread(target=_worker_loop, daemon=True, name="jobs-worker")
    _worker_thread.start()
    logger.info("jobs worker started")

def stop_worker():
    _worker_stop.set()
    if _worker_thread:
        _worker_thread.join(timeout=2)
