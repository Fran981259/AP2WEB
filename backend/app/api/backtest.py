"""Backtest routes — every run is a durable job, never a daemon thread."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Path, Request
from fastapi.routing import APIRouter

from ..auth import current_user, require_permission
from ..ratelimit import rate_limit
from .deps import audit, clamp_limit, csrf_protect, user_id

router = APIRouter()


def _create_backtest_job(user: dict, mode: str, interval_hours: float | None = None,
                         league_ids: list[int] | None = None) -> dict:
    from ..jobs import create_job

    params: dict = {"mode": mode}
    if interval_hours is not None:
        params["interval_hours"] = interval_hours
    if league_ids:
        params["league_ids"] = league_ids
    uid = user_id(user["username"])
    try:
        return create_job("backtest", requested_by=uid, parameters=params)
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))


def _active_backtest_jobs() -> list[dict]:
    from ..jobs import list_jobs

    return [j for j in list_jobs(limit=50, job_type="backtest")
            if j.get("status") in ("pending", "running")]


@router.post("/api/backtest/start", tags=["backtest"])
def backtest_start(request: Request,
                   user: dict = Depends(require_permission("run:backtest")),
                   _: None = Depends(csrf_protect),
                   __: None = Depends(rate_limit("backtest")),
                   interval_hours: float = 6.0):
    """Inicia um ciclo de backtest como JOB persistente (sem thread daemon)."""
    interval_hours = min(max(interval_hours, 0.5), 24 * 30)
    job = _create_backtest_job(user, "start", interval_hours=interval_hours)
    audit(user, "backtest.start", request, resource_type="job", resource_id=job["id"],
          metadata={"interval_hours": interval_hours})
    return {"ok": True, "job": job, "job_id": job["id"]}


@router.post("/api/backtest/stop", tags=["backtest"])
def backtest_stop(request: Request,
                  user: dict = Depends(require_permission("run:backtest")),
                  _: None = Depends(csrf_protect),
                  __: None = Depends(rate_limit("backtest"))):
    """Cancela jobs de backtest ativos (persistido na tabela de jobs)."""
    from ..jobs import cancel_job

    cancelled = []
    for j in _active_backtest_jobs():
        j = cancel_job(j["id"], {"username": user["username"], "role": user["role"],
                                 "user_id": user.get("user_id")})
        cancelled.append(j["id"])
    audit(user, "backtest.stop", request, resource_type="job",
          metadata={"cancelled_ids": cancelled})
    return {"ok": True, "cancelled": cancelled}


@router.get("/api/backtest/status", tags=["backtest"])
def backtest_status(user: str = Depends(current_user)):
    """Status de backtest — leitura do jobs table (read-only compat)."""
    from ..jobs import list_jobs

    active = _active_backtest_jobs()
    recent = list_jobs(limit=10, job_type="backtest")
    return {
        "running": bool(active),
        "active_jobs": active,
        "jobs": recent,
    }


@router.post("/api/backtest/run", tags=["backtest"])
def backtest_run(request: Request,
                 league_ids: list[int] | None = None,
                 user: dict = Depends(require_permission("run:backtest")),
                 _: None = Depends(csrf_protect),
                 __: None = Depends(rate_limit("backtest"))):
    """Executa um ciclo de backtest em ligas específicas como JOB persistente."""
    cleaned = None
    if league_ids:
        cleaned = [int(x) for x in league_ids if int(x) > 0][:200]
    job = _create_backtest_job(user, "run", league_ids=cleaned)
    audit(user, "backtest.run", request, resource_type="job", resource_id=job["id"],
          metadata={"leagues": cleaned})
    return {"ok": True, "job": job, "job_id": job["id"]}


@router.get("/api/backtest/cv/{league_id}", tags=["backtest"])
def backtest_temporal_cv(league_id: int = Path(gt=0), n_folds: int = 5,
                         user: str = Depends(current_user)):
    n_folds = clamp_limit(n_folds, 20)
    from ..backtest import run_temporal_cv
    return run_temporal_cv(league_id, n_folds)


@router.get("/api/backtest/history", tags=["backtest"])
def backtest_history(limit: int = 20, user: str = Depends(current_user)):
    from ..backtest import get_loop
    limit = clamp_limit(limit, 200)
    loop = get_loop()
    history = loop.get_history(limit)
    return {"history": history, "total": len(loop.get_history(1000))}


@router.get("/api/backtest/meta", tags=["backtest"])
def backtest_meta(user: str = Depends(current_user)):
    from ..backtest import get_loop
    loop = get_loop()
    return {
        "total_records": len(loop.meta.history),
        "recent": loop.meta.history[-50:],
    }


@router.get("/api/backtest/summary", tags=["backtest"])
def backtest_summary(user: str = Depends(current_user)):
    from ..backtest import get_loop
    return get_loop().get_summary()
