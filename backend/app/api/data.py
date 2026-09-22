"""Read-only league, team, match and data-quality routes."""
from __future__ import annotations

from fastapi import Depends, Path
from fastapi.routing import APIRouter

from .. import data_quality, db
from .. import sofascore as sofascore_data
from ..auth import current_user, current_user_with_role

router = APIRouter()


@router.get("/api/leagues", tags=["data"])
def leagues(user: str = Depends(current_user)):
    return sofascore_data.leagues()


@router.get("/api/data/quality", tags=["data"])
def data_quality_report(user: dict = Depends(current_user_with_role)):
    """Quality gates by league; read-only and safe for every authenticated user."""
    items = data_quality.league_quality()
    return {
        "items": items,
        "summary": {
            "ready": sum(item["status"] == "ready" for item in items),
            "total": len(items),
            "statuses": {status: sum(item["status"] == status for item in items)
                         for status in ("ready", "no_data", "stale", "incomplete", "insufficient_history")},
        },
    }


@router.get("/api/leagues/{league_id}/teams", tags=["data"])
def league_teams(league_id: int = Path(gt=0), user: str = Depends(current_user)):
    return [dict(r) for r in db.run_query(
        "SELECT t.id, t.name, "
        "(SELECT COUNT(*) FROM matches m WHERE (m.home_team_id=t.id OR m.away_team_id=t.id) "
        "  AND m.league_id=? AND m.status='played') AS games_played "
        "FROM teams t WHERE t.league_id=? ORDER BY t.name",
        (league_id, league_id))]


@router.get("/api/leagues/{league_id}/matches", tags=["data"])
def league_matches(league_id: int = Path(gt=0), user: str = Depends(current_user)):
    return [dict(r) for r in db.run_query(
        "SELECT m.id, m.kickoff_datetime, m.round, m.status, m.score_home, m.score_away, "
        "m.xg_home, m.xg_away, th.name AS home, ta.name AS away "
        "FROM matches m JOIN teams th ON th.id=m.home_team_id "
        "JOIN teams ta ON ta.id=m.away_team_id "
        "WHERE m.league_id=? ORDER BY m.kickoff_datetime DESC, m.id LIMIT 200",
        (league_id,))]
