"""Learning routes: calibration jobs, model status and learning curves."""
from __future__ import annotations

import logging

from fastapi import Depends, HTTPException, Path, Request
from fastapi.routing import APIRouter

from .. import db
from ..auth import current_user, require_permission
from ..learning import calibration_status, model_status, motor_curve
from ..ratelimit import rate_limit
from .deps import audit, csrf_protect, user_id

logger = logging.getLogger("ap2web")
router = APIRouter()


@router.post("/api/learning/calibrate", tags=["learning"])
def learning_calibrate(request: Request, user: dict = Depends(require_permission("run:calibration")),
                       _: None = Depends(csrf_protect), __: None = Depends(rate_limit("calibrate"))):
    audit(user, "learning.calibrate_all", request, resource_type="job")
    logger.info("calibrate_all job by %s", user["username"])
    from ..jobs import create_job
    try:
        uid = user_id(user["username"])
    except Exception:
        uid = 0
    try:
        job = create_job("calibrate_all", requested_by=uid, parameters={})
        return {"ok": True, "job": job, "job_id": job["id"]}
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/api/learning/calibrate/{league_id}", tags=["learning"])
def learning_calibrate_league(league_id: int = Path(gt=0), request: Request = None,
                              user: dict = Depends(require_permission("run:calibration")),
                              _: None = Depends(csrf_protect),
                              __: None = Depends(rate_limit("calibrate"))):
    audit(user, "learning.calibrate_league", request, resource_type="league", resource_id=league_id)
    from ..jobs import create_job
    cnt = db.run_query("SELECT COUNT(*) c FROM matches WHERE league_id=? AND status='played'", (league_id,))
    if cnt and cnt[0]["c"] < 5:
        raise HTTPException(status_code=400, detail="Liga sem dados suficientes")
    try:
        uid = user_id(user["username"])
    except Exception:
        uid = 0
    try:
        job = create_job("calibrate_league", requested_by=uid, league_id=league_id,
                         parameters={"league_id": league_id})
        return {"ok": True, "job": job, "job_id": job["id"]}
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/api/learning/calibrate/status", tags=["learning"])
def learning_calibrate_status(user: str = Depends(current_user)):
    return calibration_status()


@router.get("/api/learning/status", tags=["learning"])
def learning_status(user: str = Depends(current_user)):
    return model_status()


@router.get("/api/learning/curve", tags=["learning"])
def learning_curve(user: str = Depends(current_user)):
    return motor_curve()


@router.get("/api/learning/backtest/{league_id}", tags=["learning"])
def learning_backtest(league_id: int = Path(gt=0), user: str = Depends(current_user)):
    from ..backtest import run_single_league_backtest
    return run_single_league_backtest(league_id)


@router.get("/api/learning/xgb/{league_id}", tags=["learning"])
def learning_xgb_comparison(league_id: int = Path(gt=0), user: str = Depends(current_user)):
    """BASE.md §26-27: comparação honesta XGBoost vs Poisson (walk-forward temporal)."""
    from ..xgb_engine import compare_models
    return compare_models(league_id)
