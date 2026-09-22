"""Market routes: odds ingestion and 1X2 market reads."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Path, Request
from fastapi.routing import APIRouter

from ..auth import current_user, require_permission
from ..ratelimit import rate_limit
from .deps import audit, clamp_limit, csrf_protect, user_id
from .models import OddsQuoteBody

router = APIRouter()


@router.post("/api/odds/sync", tags=["market"])
def odds_sync(sport_key: str, request: Request,
              region: str = "eu", user: dict = Depends(require_permission("sync:data")),
              _: None = Depends(csrf_protect), __: None = Depends(rate_limit("sync"))):
    """Enfileira ingestão auditável de odds 1X2 da The Odds API."""
    from ..jobs import create_job
    audit(user, "odds.sync", request, resource_type="job")
    try:
        job = create_job("sync_odds", requested_by=user_id(user["username"]),
                         parameters={"sport_key": sport_key, "region": region})
        return {"ok": True, "job": job, "job_id": job["id"]}
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get("/api/market/{match_id}", tags=["market"])
def market_match(match_id: int = Path(gt=0), as_of: str | None = None,
                 user: str = Depends(current_user)):
    from ..market import market_for_match
    try:
        return market_for_match(match_id, as_of)
    except IndexError:
        raise HTTPException(status_code=404, detail="Partida não encontrada")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/api/market/{match_id}/quotes", status_code=201, tags=["market"])
def market_quote(match_id: int, body: OddsQuoteBody,
                 user: dict = Depends(require_permission("sync:data")),
                 _: None = Depends(csrf_protect), __: None = Depends(rate_limit("sync"))):
    from ..odds_store import save_1x2_quote
    try:
        save_1x2_quote(match_id, body.provider, body.captured_at, body.odds, body.source_event_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "match_id": match_id, "market_type": "1x2"}


@router.get("/api/market/league/{league_id}", tags=["market"])
def market_league(league_id: int = Path(gt=0), limit: int = 20,
                  as_of: str | None = None,
                  user: str = Depends(current_user)):
    from ..market import market_league
    return market_league(league_id, clamp_limit(limit, 100), as_of)
