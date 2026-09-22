"""Job inspection and cancellation routes."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Path, Request
from fastapi.routing import APIRouter

from ..auth import current_user_with_role, require_permission
from ..ratelimit import rate_limit
from .deps import audit, clamp_limit, csrf_protect, user_id

router = APIRouter()


@router.get("/api/jobs/{job_id}", tags=["jobs"])
def get_job_endpoint(job_id: int = Path(gt=0), user: dict = Depends(current_user_with_role)):
    from ..jobs import get_job
    j = get_job(job_id)
    if not j:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    if user.get("role") != "admin" and j.get("requested_by") != user_id(user["username"]):
        raise HTTPException(status_code=403, detail="Permissão negada")
    return j


@router.get("/api/jobs", tags=["jobs"])
def list_jobs_endpoint(limit: int = 20, job_type: str | None = None,
                       user: dict = Depends(current_user_with_role)):
    from ..jobs import list_jobs
    limit = clamp_limit(limit, 100)
    scoped = None if user.get("role") == "admin" else user_id(user["username"])
    return list_jobs(user_id=scoped, limit=limit, job_type=job_type)


@router.post("/api/jobs/{job_id}/cancel", tags=["jobs"])
def cancel_job_endpoint(job_id: int = Path(gt=0), request: Request = None,
                        user: dict = Depends(require_permission("job:cancel")),
                        _: None = Depends(csrf_protect),
                        __: None = Depends(rate_limit("job_cancel"))):
    from ..jobs import cancel_job
    try:
        j = cancel_job(job_id, {"username": user["username"], "role": user["role"],
                                "user_id": user_id(user["username"])})
        audit(user, "jobs.cancel", request, resource_type="job", resource_id=job_id,
              metadata={"status": j.get("status")})
        return j
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permissão negada")
    except LookupError:
        raise HTTPException(status_code=404, detail="Job não encontrado")
