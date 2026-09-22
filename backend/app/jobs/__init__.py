"""Persistent job system — DB-backed, survives restart, no daemon-only state."""
from __future__ import annotations

from .loop import run_worker_loop, start_worker, stop_worker
from .registry import (
    ALLOWED_TYPES,
    _JobCancelled,
    _idempotency_key,
    _lease_until,
    _user_id_by_name,
    cancel_job,
    claim_job,
    complete_job,
    create_job,
    fail_job,
    get_job,
    job_metrics,
    list_jobs,
    recover_expired_jobs,
    renew_job_lease,
    update_progress,
)
from .runner import _run_one
from .workers import (
    heartbeat_worker,
    register_worker,
    stop_worker_record,
    worker_healthy,
)

__all__ = [
    "ALLOWED_TYPES",
    "_JobCancelled",
    "_idempotency_key",
    "_lease_until",
    "_run_one",
    "_user_id_by_name",
    "cancel_job",
    "claim_job",
    "complete_job",
    "create_job",
    "fail_job",
    "get_job",
    "heartbeat_worker",
    "job_metrics",
    "list_jobs",
    "recover_expired_jobs",
    "register_worker",
    "renew_job_lease",
    "run_worker_loop",
    "start_worker",
    "stop_worker",
    "stop_worker_record",
    "update_progress",
    "worker_healthy",
]
