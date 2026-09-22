"""Public prediction entry points: match, league upcoming, fixture."""
from __future__ import annotations

from datetime import datetime, timezone

from .. import db
from ..columns import MATCHES, prefixed
from .builder import _build


def predict_match(match_id: int, as_of_timestamp: str | None = None, use_bayesian: bool | None = None) -> dict:
    # O jogo previsto deve sempre ser encontrado; o filtro as-of aplica-se
    # apenas ao histórico usado nas features (dentro de _build).
    query = (
        f"SELECT {prefixed(MATCHES, 'm')}, l.name AS league_name, "
        "th.name AS home_name, ta.name AS away_name "
        "FROM matches m "
        "JOIN leagues l ON l.id=m.league_id "
        "JOIN teams th ON th.id=m.home_team_id "
        "JOIN teams ta ON ta.id=m.away_team_id "
        "WHERE m.id=?"
    )
    rows = db.run_query(query, (match_id,))
    if not rows:
        raise IndexError("Partida não encontrada")
    m = rows[0]
    kickoff = m["kickoff_datetime"]
    cutoff = as_of_timestamp or kickoff
    if as_of_timestamp and kickoff:
        try:
            if datetime.fromisoformat(as_of_timestamp.replace("Z", "+00:00")) > datetime.fromisoformat(kickoff.replace("Z", "+00:00")):
                raise ValueError("as_of_timestamp cannot be after the match kickoff")
        except ValueError as exc:
            if str(exc).startswith("as_of_timestamp"):
                raise
            raise ValueError("as_of_timestamp must be ISO-8601") from exc
    return _build(m["league_id"], m["home_team_id"], m["away_team_id"],
                  m["home_name"], m["away_name"], m["league_name"], m, cutoff, use_bayesian)
def predict_league_upcoming(league_id: int, limit: int = 10,
                             as_of_timestamp: str | None = None, use_bayesian: bool | None = None) -> list[dict]:
    condition = "AND status='scheduled' AND datetime(kickoff_datetime) >= datetime(?)"
    params = (league_id, as_of_timestamp or datetime.now(timezone.utc).isoformat(), limit)
    query = (
        "SELECT id FROM matches WHERE league_id=? {condition} "
        "ORDER BY kickoff_datetime, id LIMIT ?"
    ).format(condition=condition)
    rows = db.run_query(query, params)
    return [predict_match(r["id"], as_of_timestamp, use_bayesian) for r in rows]
def predict_fixture(league_id: int, home_team_id: int, away_team_id: int,
                    as_of_timestamp: str | None = None, use_bayesian: bool | None = None) -> dict:
    league = db.run_query("SELECT id, name, country FROM leagues WHERE id=?", (league_id,))[0]
    rows = db.run_query(
        "SELECT id, name FROM teams WHERE league_id=? AND id IN (?,?)",
        (league_id, home_team_id, away_team_id))
    names = {r["id"]: r["name"] for r in rows}
    if not names or home_team_id not in names or away_team_id not in names:
        raise IndexError("Confronto não encontrado")
    return _build(league_id, home_team_id, away_team_id,
                  names[home_team_id], names[away_team_id], league["name"],
                  as_of_timestamp=as_of_timestamp, use_bayesian=use_bayesian)
