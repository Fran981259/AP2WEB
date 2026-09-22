"""Standalone job worker process (production).

The ONLY supported background execution model for production: a separate
process, explicitly configured, independently observable (via ``/api/jobs`` and
the ``jobs`` table), and connected to the same persistent job store as the API
processes.

Run with:

    python -m backend.app.worker

It polls the DB for pending jobs and executes them (sync, calibration,
backtest). Stop gracefully with SIGTERM/SIGINT:
    kill -TERM <pid>
"""
from __future__ import annotations

import logging
import threading

from .config import settings
from . import db
from .jobs import run_worker_loop

logger = logging.getLogger("ap2web.worker")


def main() -> int:
    stop = threading.Event()
    import signal


    def _signal(signum, _frame):  # pragma: no cover - signal handler
        logger.info("worker received signal %s — shutting down", signum)
        stop.set()

    signal.signal(signal.SIGTERM, _signal)
    signal.signal(signal.SIGINT, _signal)

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logger.info("AP2WEB job worker starting (mode=%s)", db.MODE)
    db.init_db()
    worker_id = f"worker-{__import__('uuid').uuid4().hex[:12]}"
    logger.info("database ready — polling jobs id=%s", worker_id)
    try:
        run_worker_loop(stop, worker_id, settings.worker_heartbeat_seconds,
                        settings.worker_lease_seconds)
    except Exception:
        logger.exception("worker crashed")
        return 1
    logger.info("worker stopped cleanly")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
