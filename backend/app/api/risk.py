"""Risk Engine routes (FASE 11): per-match and portfolio exposure."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Path
from fastapi.routing import APIRouter

from ..auth import current_user
from ..ratelimit import rate_limit
from .deps import clamp_limit, csrf_protect

router = APIRouter()


def _risk_config(kelly_fraction: float, bankroll: float):
    from ..risk import RiskConfig
    return RiskConfig(kelly_fraction=min(max(kelly_fraction, 0.0), 1.0),
                      bankroll=max(bankroll, 1.0))


@router.get("/api/risk/{match_id}", tags=["risk"])
def risk_match(match_id: int = Path(gt=0), as_of: str | None = None,
               kelly_fraction: float = 0.25,
               bankroll: float = 1000.0,
               user: str = Depends(current_user)):
    from ..risk import risk_for_match
    cfg = _risk_config(kelly_fraction, bankroll)
    try:
        return risk_for_match(match_id, cfg, as_of)
    except IndexError:
        raise HTTPException(status_code=404, detail="Partida não encontrada")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/api/risk/league/{league_id}", tags=["risk"])
def risk_league_endpoint(league_id: int = Path(gt=0), limit: int = 20,
                         as_of: str | None = None,
                         kelly_fraction: float = 0.25,
                         bankroll: float = 1000.0,
                         user: str = Depends(current_user)):
    from ..risk import risk_league
    return risk_league(league_id, clamp_limit(limit, 100),
                       _risk_config(kelly_fraction, bankroll), as_of)


@router.post("/api/risk/portfolio", tags=["risk"])
def risk_portfolio(matches: list[int], kelly_fraction: float = 0.25,
                   bankroll: float = 1000.0,
                   user: str = Depends(current_user),
                   _: None = Depends(csrf_protect),
                   __: None = Depends(rate_limit("prediction"))):
    from ..risk import portfolio_risk, risk_for_match
    clean = [int(m) for m in (matches or []) if int(m) > 0][:100]
    cfg = _risk_config(kelly_fraction, bankroll)
    matches_risk = [risk_for_match(mid, cfg) for mid in clean]
    return portfolio_risk(matches_risk, cfg)
