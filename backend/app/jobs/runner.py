"""Job runner: executes one persisted job to completion."""
from __future__ import annotations

import json
import logging
import time
import uuid

from .. import db
from .registry import (
    _JobCancelled,
    claim_job,
    complete_job,
    fail_job,
    get_job,
    renew_job_lease,
    update_progress,
)

logger = logging.getLogger("ap2web.jobs")


def _run_one(job: dict, worker_id: str | None = None, lease_seconds: int = 60):
    jid = job["id"]
    jtype = job["job_type"]
    raw_params = job.get("parameters") or "{}"
    params = json.loads(raw_params) if isinstance(raw_params, str) else raw_params
    wid = worker_id or f"worker-{uuid.uuid4().hex[:6]}"
    if not claim_job(jid, wid, lease_seconds):
        return
    try:
        def heartbeat() -> None:
            renew_job_lease(jid, wid, lease_seconds)

        if jtype == "sync_all":
            from ..sofascore import sync_league, load_leagues

            leagues = load_leagues()
            total = len(leagues)
            results = []
            for i, cfg in enumerate(leagues):
                cur = get_job(jid)
                if cur and cur["status"] == "cancelled":
                    logger.info("job %s cancelled mid-run", jid)
                    return
                update_progress(jid, (i) / total if total else 1.0, worker_id=wid, lease_seconds=lease_seconds)
                try:
                    update_progress(
                        jid, (i) / total if total else 1.0,
                        detail=f"Sincronizando {cfg.get('name', 'liga')}",
                        worker_id=wid, lease_seconds=lease_seconds,
                    )
                    r = sync_league(cfg, heartbeat=heartbeat)
                    results.append({"league": cfg.get("name"), **r})
                except Exception as e:
                    logger.exception("sync league %s failed", cfg.get("name"))
                    results.append({"league": cfg.get("name"), "ok": False, "error": str(e)})
                update_progress(
                    jid, (i + 1) / total if total else 1.0,
                    detail=f"Concluída {cfg.get('name', 'liga')}",
                    worker_id=wid, lease_seconds=lease_seconds,
                )
                time.sleep(0.2)
            failed = [result for result in results if not result.get("ok")]
            res = {"ok": not failed, "synced": total - len(failed), "total": total,
                   "failed": failed, "results": results}
            if failed:
                fail_job(jid, f"{len(failed)} of {total} league syncs failed or were partial", result=res)
            else:
                try:
                    from ..prediction import invalidate_prediction_cache
                    invalidate_prediction_cache(None)
                except Exception:
                    pass
                complete_job(jid, res)
        elif jtype == "sync_league":
            from ..sofascore import sync_league_local
            league_id = job["league_id"]
            r = sync_league_local(league_id, heartbeat=heartbeat)
            if not r.get("ok"):
                fail_job(jid, r.get("error", "league sync was partial"), result=r)
            else:
                try:
                    from ..prediction import invalidate_prediction_cache
                    invalidate_prediction_cache(league_id)
                except Exception:
                    pass
                complete_job(jid, r)

        elif jtype == "sync_odds":
            from ..the_odds_api import sync_soccer_h2h
            sport_key = params.get("sport_key")
            if not sport_key:
                raise ValueError("sync_odds requires sport_key")
            r = sync_soccer_h2h(sport_key, params.get("region", "eu"))
            if not r.get("ok"):
                raise RuntimeError(r.get("reason", "odds sync failed"))
            complete_job(jid, r)
        elif jtype == "calibrate_all":
            from ..learning import calibrate_all
            r = calibrate_all()
            try:
                from ..prediction import invalidate_prediction_cache
                invalidate_prediction_cache(None)
            except Exception:
                pass
            complete_job(jid, r)
        elif jtype == "calibrate_league":
            from ..learning import calibrate_league
            r = calibrate_league(job["league_id"])
            try:
                from ..prediction import invalidate_prediction_cache
                invalidate_prediction_cache(job["league_id"])
            except Exception:
                pass
            complete_job(jid, r or {"ok": False})
        elif jtype == "backtest":
            from ..backtest import get_loop
            params = json.loads(job["parameters"] or "{}")
            league_ids = params.get("league_ids")

            def _progress(idx: int, total: int, league_id) -> None:
                cur = get_job(jid)
                if cur and cur["status"] == "cancelled":
                    logger.info("job %s cancelled mid-run", jid)
                    raise _JobCancelled()
                update_progress(jid, (idx / total) if total else 1.0,
                                detail=f"liga {league_id}", worker_id=wid,
                                lease_seconds=lease_seconds)

            try:
                r = get_loop()._execute_cycle(league_ids, progress_cb=_progress, source_job_id=jid)
                cur = get_job(jid)
                if cur and cur["status"] == "cancelled":
                    logger.info("job %s cancelled mid-run", jid)
                    return
                complete_job(jid, r)
            except _JobCancelled:
                return
        elif jtype == "health":
            complete_job(jid, {"database": db.run_query("SELECT 1 AS ok")[0]["ok"] == 1})
        else:
            raise ValueError(f"Unsupported persisted job type: {jtype}")
    except Exception as e:
        logger.exception("job %s failed", jid)
        fail_job(jid, str(e)[:2000])
