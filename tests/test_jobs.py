"""Persistent job system + legacy-background-path removal tests.

These validate the production execution model: every background task runs as a
durable DB job consumed by the worker (in-process opt-in or the standalone
``python -m backend.app.worker`` process), and the old daemon-thread APIs are
deprecated (raise instead of silently starting a thread).
"""
from __future__ import annotations

import threading

from backend.app import db, jobs


def _admin_user():
    rows = db.run_query("SELECT id, username FROM users WHERE username=?", ("admin",))
    if rows:
        return {"user_id": rows[0]["id"], "username": "admin", "role": "admin"}
    from backend.app import auth

    db.run_exec(
        "INSERT INTO users(username, password_hash, role, is_active) VALUES(?,?,?,1)",
        ("admin", auth.hash_password("admin-teste-jobs-secret"), "admin"),
    )
    rows = db.run_query("SELECT id, username FROM users WHERE username=?", ("admin",))
    return {"user_id": rows[0]["id"], "username": "admin", "role": "admin"}


def test_create_duplicate_idempotent():
    u = _admin_user()
    assert u is not None
    first = jobs.create_job("health", requested_by=u["user_id"], parameters={"v": 1})
    second = jobs.create_job("health", requested_by=u["user_id"], parameters={"v": 1})
    assert first["id"] == second["id"]
    assert first["status"] == "pending"


def test_single_active_guard_for_calibrate_all():
    u = _admin_user()
    active = jobs.list_jobs(limit=10, job_type="calibrate_all")
    # ensure no leftover active job from previous runs
    for j in active:
        if j["status"] in ("pending", "running"):
            jobs.cancel_job(j["id"], u)
    first = jobs.create_job("calibrate_all", requested_by=u["user_id"], parameters={"batch": 1})
    assert first["status"] == "pending"
    import pytest

    # distinct idempotency key → single-active guard must reject the second one
    with pytest.raises(RuntimeError):
        jobs.create_job("calibrate_all", requested_by=u["user_id"], parameters={"batch": 2})
    try:
        jobs.cancel_job(first["id"], u)
    except LookupError:
        pass


def test_worker_loop_stops_on_signal():
    u = _admin_user()
    jobs.create_job("health", requested_by=u["user_id"], parameters={"act": 1})
    stop = threading.Event()
    stop.set()
    jobs.run_worker_loop(stop)  # must return promptly when stop is signalled
    assert isinstance(jobs.job_metrics(), dict)


def test_direct_run_completes_job():
    u = _admin_user()
    job = jobs.create_job("health", requested_by=u["user_id"], parameters={"act": 2})
    jobs._run_one(job)
    got = jobs.get_job(job["id"])
    assert got["status"] == "completed"


def test_cancellation_persists_and_blocks_execution():
    u = _admin_user()
    job = jobs.create_job("health", requested_by=u["user_id"], parameters={"act": 3})
    jobs.cancel_job(job["id"], u)
    got = jobs.get_job(job["id"])
    assert got["status"] == "cancelled"
    # cancelled job is not claimed by the worker
    jobs._run_one(got)
    assert jobs.get_job(job["id"])["status"] == "cancelled"


def test_expired_running_jobs_are_recovered():
    u = _admin_user()
    job = jobs.create_job("health", requested_by=u["user_id"], parameters={"act": 4})
    jobs.claim_job(job["id"], "dead-worker", lease_seconds=10)
    assert jobs.get_job(job["id"])["status"] == "running"
    db.run_exec("UPDATE jobs SET lease_expires_at='2000-01-01T00:00:00+00:00' WHERE id=?", (job["id"],))
    jobs.recover_expired_jobs()
    got = jobs.get_job(job["id"])
    assert got["status"] == "failed"
    assert "recovered" in got.get("error_message", "")


def test_worker_heartbeat_and_job_lease_are_durable():
    jobs.register_worker("test-worker")
    assert jobs.worker_healthy(5) is True
    u = _admin_user()
    job = jobs.create_job("health", requested_by=u["user_id"], parameters={"act": 5})
    assert jobs.claim_job(job["id"], "test-worker", lease_seconds=10) is True
    assert jobs.renew_job_lease(job["id"], "test-worker", lease_seconds=10) is True
    active = jobs.get_job(job["id"])
    assert active["worker_id"] == "test-worker"
    assert active["lease_expires_at"] is not None
    jobs.stop_worker_record("test-worker")
    assert jobs.worker_healthy(5) is False


def test_sync_job_renews_short_lease_during_league_work(monkeypatch):
    u = _admin_user()
    job = jobs.create_job("sync_all", requested_by=u["user_id"], parameters={"lease": "short"})
    calls = []
    renewals = []

    original_renew = jobs.renew_job_lease

    def renew(job_id, worker_id, lease_seconds=60):
        renewals.append((job_id, worker_id, lease_seconds))
        return original_renew(job_id, worker_id, lease_seconds)

    monkeypatch.setattr("backend.app.sofascore_data.load_leagues", lambda: [{"name": "Test", "id": 1}])
    monkeypatch.setattr(jobs, "renew_job_lease", renew)

    def sync(cfg, heartbeat=None):
        assert heartbeat is not None
        heartbeat()
        calls.append(cfg["id"])
        return {"ok": True}

    monkeypatch.setattr("backend.app.sofascore_data.sync_league", sync)
    jobs._run_one(job, worker_id="short-lease-worker", lease_seconds=1)

    assert calls == [1]
    assert len(renewals) >= 2
    assert all(renewal[2] == 1 for renewal in renewals)
    assert jobs.get_job(job["id"])["status"] == "completed"


def test_sync_league_is_blocked_while_sync_all_is_active():
    u = _admin_user()
    full = jobs.create_job("sync_all", requested_by=u["user_id"], parameters={"admission": 1})
    assert jobs.claim_job(full["id"], "full-sync-worker") is True

    import pytest

    with pytest.raises(RuntimeError, match="Full sync already active"):
        jobs.create_job("sync_league", requested_by=u["user_id"], league_id=12345,
                        parameters={"admission": 1})
    jobs.complete_job(full["id"], {})


def test_completed_job_can_be_repeated():
    u = _admin_user()
    first = jobs.create_job("health", requested_by=u["user_id"], parameters={"repeat": 1})
    jobs._run_one(first)
    second = jobs.create_job("health", requested_by=u["user_id"], parameters={"repeat": 1})
    assert second["id"] != first["id"]
    assert second["status"] == "pending"


def test_cancelled_running_job_is_not_completed_later():
    u = _admin_user()
    job = jobs.create_job("health", requested_by=u["user_id"], parameters={"cancel_race": 1})
    assert jobs.claim_job(job["id"], "test-worker")
    jobs.cancel_job(job["id"], u)
    jobs.complete_job(job["id"], {"late": True})
    jobs.fail_job(job["id"], "late failure")
    assert jobs.get_job(job["id"])["status"] == "cancelled"


def test_api_schema_startup_does_not_kill_live_job():
    u = _admin_user()
    job = jobs.create_job("health", requested_by=u["user_id"], parameters={"live": 1})
    assert jobs.claim_job(job["id"], "live-worker")
    db.init_db()
    assert jobs.get_job(job["id"])["status"] == "running"
    jobs.complete_job(job["id"], {})
