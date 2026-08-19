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
    if rows:
        gf = sum(r["gf"] or 0 for r in rows) / len(rows)
        ga = sum(r["ga"] or 0 for r in rows) / len(rows)
        return {"gf_avg": round(gf, 3), "ga_avg": round(ga, 3)}

    # Fallback robusto: calcula médias reais de GF/GA a partir dos placares jogados.
    gfs, gas = [], []
    for m in db.run_query(
            "SELECT ft_home, ft_away, home_team_id FROM matches "
            "WHERE league_id=? AND (home_team_id=? OR away_team_id=?) "
            "  AND status='played' AND ft_home IS NOT NULL "
            "ORDER BY match_date DESC LIMIT 10",
            (league_id, team_id, team_id)):
        if m["home_team_id"] == team_id:
            gfs.append(m["ft_home"]); gas.append(m["ft_away"])
        else:
            gfs.append(m["ft_away"]); gas.append(m["ft_home"])
    if gfs:
        return {"gf_avg": round(sum(gfs) / len(gfs), 3),
                "ga_avg": round(sum(gas) / len(gas), 3)}
    return {"gf_avg": 1.2, "ga_avg": 1.2}


def _recent_form(league_id: int, team_id: int, limit: int = 5) -> list[dict]:
    """Últimos resultados do time na liga (para a comparação lado a lado)."""
    rows = db.run_query(
        "SELECT m.match_date, m.ft_home, m.ft_away, m.status, "
        "       m.home_team_id, m.away_team_id, "
        "       th.name AS home, ta.name AS away "
        "FROM matches m "
        "JOIN teams th ON th.id=m.home_team_id "
        "JOIN teams ta ON ta.id=m.away_team_id "
        "WHERE m.league_id=? AND (m.home_team_id=? OR m.away_team_id=?) "
        "  AND m.status='played' AND m.ft_home IS NOT NULL "
        "ORDER BY m.match_date DESC LIMIT ?",
        (league_id, team_id, team_id, limit))
    out = []
    for r in rows:
        played_home = r["home_team_id"] == team_id
        gf = r["ft_home"] if played_home else r["ft_away"]
        ga = r["ft_away"] if played_home else r["ft_home"]
        out.append({
            "date": r["match_date"],
            "opponent": r["away"] if played_home else r["home"],
            "played_home": played_home,
            "gf": gf,
            "ga": ga,
            "result": "W" if gf > ga else ("D" if gf == ga else "L"),
        })
    return out


def _h2h(league_id: int, home_team_id: int, away_team_id: int, limit: int = 5) -> list[dict]:
    """Confrontos diretos entre os dois times (qualquer lado)."""
    rows = db.run_query(
        "SELECT m.match_date, m.ft_home, m.ft_away, th.name AS home, ta.name AS away "
        "FROM matches m "
        "JOIN teams th ON th.id=m.home_team_id "
        "JOIN teams ta ON ta.id=m.away_team_id "
        "WHERE m.league_id=? AND m.status='played' AND m.ft_home IS NOT NULL "
        "  AND ((m.home_team_id=? AND m.away_team_id=?) OR (m.home_team_id=? AND m.away_team_id=?)) "
        "ORDER BY m.match_date DESC LIMIT ?",
        (league_id, home_team_id, away_team_id, away_team_id, home_team_id, limit))
    return [dict(r) for r in rows]


def _team_card(league_id: int, team_id: int, name: str, stats: dict) -> dict:
    """Resumo de um time para comparação: médias + últimos jogos."""
    gp = 0
    for side in ("home", "away"):
        row = db.run_query(
            "SELECT COUNT(*) c FROM matches m JOIN team_stats ts ON ts.match_id=m.id "
            "WHERE m.league_id=? AND ts.team_id=? AND m.status='played' AND ts.scope=?",
            (league_id, team_id, side))
        gp += row[0]["c"] or 0
    return {
        "name": name,
        "gf_avg": stats.get("gf_avg", 0),
        "ga_avg": stats.get("ga_avg", 0),
        "games": gp,
        "form": _recent_form(league_id, team_id),
    }


def _compare(league_id: int, home_id: int, away_id: int,
             home_name: str, away_name: str, home_stats: dict, away_stats: dict) -> dict:
    return {
        "home": _team_card(league_id, home_id, home_name, home_stats),
        "away": _team_card(league_id, away_id, away_name, away_stats),
        "h2h": _h2h(league_id, home_id, away_id),
    }


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
            "league_id": m["league_id"],
            "date": m["match_date"],
            "kickoff": m["kickoff"],
            "home": m["home_name"],
            "home_id": m["home_team_id"],
            "away": m["away_name"],
            "away_id": m["away_team_id"],
        },
        "lambdas": result.lambdas,
        "probs": result.probs,
        "top_scores": result.top_scores,
        "proposals": result.proposals,
        "inputs": {"home": home_stats, "away": away_stats},
        "compare": _compare(m["league_id"], m["home_team_id"], m["away_team_id"],
                            m["home_name"], m["away_name"], home_stats, away_stats),
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
            "league_id": l["id"],
            "date": None,
            "kickoff": None,
            "home": names[home_team_id],
            "home_id": home_team_id,
            "away": names[away_team_id],
            "away_id": away_team_id,
        },
        "lambdas": result.lambdas,
        "probs": result.probs,
        "top_scores": result.top_scores,
        "proposals": result.proposals,
        "inputs": {"home": home_stats, "away": away_stats},
        "compare": _compare(league_id, home_team_id, away_team_id,
                            names[home_team_id], names[away_team_id], home_stats, away_stats),
    }