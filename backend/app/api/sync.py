"""Sofascore ingestion routes: enqueue sync jobs and report sync status."""
from __future__ import annotations

import logging

from fastapi import Depends, HTTPException, Path, Request
from fastapi.routing import APIRouter

from .. import db
from .. import sofascore as sofascore_data
from ..auth import current_user, current_user_with_role, require_permission
from ..ratelimit import rate_limit
from .deps import audit, csrf_protect, user_id

logger = logging.getLogger("ap2web")
router = APIRouter()


@router.post("/api/sofascore/sync", tags=["sofascore"])
def sofascore_sync(request: Request, user: dict = Depends(require_permission("sync:data")),
                   _: None = Depends(csrf_protect), __: None = Depends(rate_limit("sync"))):
    """Sincroniza todas as ligas — cria job persistente. Requer operator/admin."""
    rid = getattr(request.state, "request_id", None)
    audit(user, "sofascore.sync_all", request, resource_type="job")
    logger.info("sync_all job requested by %s rid=%s", user["username"], rid)
    from ..jobs import create_job
    try:
        uid = user_id(user["username"])
    except Exception:
        uid = 0
    try:
        job = create_job("sync_all", requested_by=uid or 0, parameters={})
        return {"ok": True, "job": job, "job_id": job["id"]}
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/api/sofascore/sync/league/{league_id}", tags=["sofascore"])
def sofascore_sync_league(league_id: int = Path(gt=0), request: Request = None,
                          user: dict = Depends(require_permission("sync:league")),
                          _: None = Depends(csrf_protect), __: None = Depends(rate_limit("sync"))):
    """Sincroniza uma liga — job persistente. Requer operator/admin."""
    audit(user, "sofascore.sync_league", request, resource_type="league", resource_id=league_id)
    logger.info("sync_league %s by %s", league_id, user["username"])
    if not db.run_query("SELECT id FROM leagues WHERE id=?", (league_id,)):
        raise HTTPException(status_code=404, detail="Liga não encontrada")
    from ..jobs import create_job
    try:
        uid = user_id(user["username"])
    except Exception:
        uid = 0
    try:
        job = create_job("sync_league", requested_by=uid, league_id=league_id,
                         parameters={"league_id": league_id})
        return {"ok": True, "job": job, "job_id": job["id"]}
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/api/sofascore/status", tags=["sofascore"])
def sofascore_status(user: dict = Depends(current_user_with_role)):
    """Return synchronization status from the durable jobs table."""
    from ..jobs import list_jobs

    recent = list_jobs(limit=10, job_type="sync_all")
    recent.extend(list_jobs(limit=10, job_type="sync_league"))
    recent.sort(key=lambda job: job.get("id", 0), reverse=True)
    active = [job for job in recent if job.get("status") in ("pending", "running")]
    return {
        "running": bool(active),
        "jobs": recent[:10],
        "active_job": active[0] if active else None,
    }


@router.get("/api/sofascore/data", tags=["sofascore"])
def sofascore_data_endpoint(league_id: int | None = None, next_round: int = 1,
                            user: str = Depends(current_user)):
    return sofascore_data.dataset(league_id, next_round=bool(next_round))
