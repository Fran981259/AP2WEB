"""Serviço de previsão — aplica o motor Poisson (model.py) aos dados raspados do banco.

Alimenta lambdas com as estatísticas médias dos times (GF/GA) guardadas em team_stats,
seguindo o conhecimento extraído da planilha AP 2.0 (núcleo: λ = ataque × defesa adversária).
"""
from __future__ import annotations

from . import db
from .model import MatchInput, TeamInput, predict as run_predict


def _avg_stats(league_id: int, team_id: int) -> dict:
    rows = db.run_query(
        "SELECT gf,ga,tg,ppg,gp FROM team_stats ts "
        "JOIN matches m ON m.id=ts.match_id "
        "WHERE m.league_id=? AND ts.team_id=? AND m.status='played' "
        "ORDER BY m.match_date DESC LIMIT 10",
        (league_id, team_id))
    if not rows:
        # fallback: stats de jogos agendados (prévia)
        rows = db.run_query(
            "SELECT gf,ga,tg,ppg,gp FROM team_stats ts "
            "JOIN matches m ON m.id=ts.match_id "
            "WHERE m.league_id=? AND ts.team_id=? ORDER BY m.match_date DESC LIMIT 10",
            (league_id, team_id))
    if not rows:
        return {"gf_avg": 1.2, "ga_avg": 1.2}
    gf = sum(r["gf"] or 0 for r in rows) / len(rows)
    ga = sum(r["ga"] or 0 for r in rows) / len(rows)
    return {"gf_avg": round(gf, 3), "ga_avg": round(ga, 3)}


def predict_match(match_id: int) -> dict:
    m = db.run_query(
        "SELECT m.*, l.name AS league_name, l.country AS league_country, "
        "       th.name AS home_name, ta.name AS away_name "
        "FROM matches m "
        "JOIN leagues l ON l.id=m.league_id "
        "JOIN teams th ON th.id=m.home_team_id "
        "JOIN teams ta ON ta.id=m.away_team_id "
        "WHERE m.id=?", (match_id,))[0]

    home_stats = _avg_stats(m["league_id"], m["home_team_id"])
    away_stats = _avg_stats(m["league_id"], m["away_team_id"])

    mi = MatchInput(
        league=m["league_name"],
        home=TeamInput(name=m["home_name"], **home_stats),
        away=TeamInput(name=m["away_name"], **away_stats),
    )
    result = run_predict(mi)

    return {
        "match": {
            "id": m["id"],
            "league": m["league_name"],
            "date": m["match_date"],
            "kickoff": m["kickoff"],
            "home": m["home_name"],
            "away": m["away_name"],
        },
        "lambdas": result.lambdas,
        "probs": result.probs,
        "top_scores": result.top_scores,
        "proposals": result.proposals,
        "inputs": {"home": home_stats, "away": away_stats},
    }


def predict_league_upcoming(league_id: int, limit: int = 10) -> list[dict]:
    rows = db.run_query(
        "SELECT id FROM matches WHERE league_id=? AND status='scheduled' "
        "ORDER BY match_date, kickoff LIMIT ?", (league_id, limit))
    return [predict_match(r["id"]) for r in rows]


def predict_fixture(league_id: int, home_team_id: int, away_team_id: int) -> dict:
    """Previsão de um confronto arbitrário (escolhido via dropdown)."""
    l = db.run_query("SELECT id, name, country FROM leagues WHERE id=?", (league_id,))[0]
    rows = db.run_query(
        "SELECT id, name FROM teams WHERE league_id=? AND id IN (?,?)",
        (league_id, home_team_id, away_team_id))
    names = {r["id"]: r["name"] for r in rows}
    if not names or home_team_id not in names or away_team_id not in names:
        raise IndexError("Confronto não encontrado")

    home_stats = _avg_stats(league_id, home_team_id)
    away_stats = _avg_stats(league_id, away_team_id)

    mi = MatchInput(
        league=l["name"],
        home=TeamInput(name=names[home_team_id], **home_stats),
        away=TeamInput(name=names[away_team_id], **away_stats),
    )
    result = run_predict(mi)

    return {
        "match": {
            "id": None,
            "league": l["name"],
            "date": None,
            "kickoff": None,
            "home": names[home_team_id],
            "away": names[away_team_id],
        },
        "lambdas": result.lambdas,
        "probs": result.probs,
        "top_scores": result.top_scores,
        "proposals": result.proposals,
        "inputs": {"home": home_stats, "away": away_stats},
    }