"""Serviço de previsão — aplica o motor Poisson (model.py) aos dados do Sofascore.

Alimenta lambdas com as médias de xG (ou gols) marcados/sofridos dos últimos N
jogos de cada time, usando a feature calibrada por liga (learning.get_model).
"""
from __future__ import annotations

from . import db
from .feature_engine import compute_team_stats, compute_match_stats
from .learning import get_model
from .model import MatchInput, TeamInput, predict as run_predict


def _window_values(match: dict, feature: str) -> tuple[float, float]:
    """Retorna (marcados, sofridos) do jogo `match` na feature especificada.
    
    Agora delega ao Feature Engine para consistência unificada.
    """
    gm = compute_match_stats(match, feature)
    return gm["gf"], gm["ga"]


def _played_rows(cols: str, extra_where: str, params: list,
                 limit: int, as_of_timestamp: str | None = None) -> list:
    """Fonte ÚNICA para busca de jogos jogados de uma liga (auditoria/temporal).

    Aplica consistentemente o filtro as-of (`date(kickoff) < date(?)`) quando
    fornecido, prevenindo data leakage em todas as consultas de previsão.
    `params` deve conter os valores de `extra_where` na ordem (league_id primeiro).
    """
    query = (
        f"SELECT {cols} "
        "FROM matches m "
        "JOIN teams th ON th.id=m.home_team_id "
        "JOIN teams ta ON ta.id=m.away_team_id "
        "WHERE m.league_id=? AND m.status='played' AND m.score_home IS NOT NULL "
        f"{extra_where} "
    )
    all_params = list(params)
    if as_of_timestamp:
        query += "AND date(m.kickoff_datetime) < date(?) "
        all_params.append(as_of_timestamp)
    query += "ORDER BY m.kickoff_datetime DESC LIMIT ?"
    all_params.append(limit)
    return db.run_query(query, tuple(all_params))


def _avg_stats(league_id: int, team_id: int, window: int, feature: str,
               as_of_timestamp: str | None = None) -> dict:
    """Computa médias de gols usando Feature Engine unificado.

    Se as_of_timestamp for fornecido, somente jogos com kickoff_datetime anterior
    são considerados (prevenção de data leakage temporal).
    """
    rows = _played_rows(
        "m.kickoff_datetime, m.home_team_id, m.away_team_id, "
        "m.score_home, m.score_away, m.xg_home, m.xg_away",
        "AND (m.home_team_id=? OR m.away_team_id=?)",
        [league_id, team_id, team_id], window, as_of_timestamp)
    gfs, gas = [], []
    for m in rows:
        row_dict = dict(m)
        # Construir dicionário de história para o Feature Engine
        hist_entry = {
            "gf": row_dict["score_home"] if row_dict["home_team_id"] == team_id else row_dict["score_away"],
            "ga": row_dict["score_away"] if row_dict["home_team_id"] == team_id else row_dict["score_home"],
            "xg_home": row_dict["xg_home"],
            "xg_away": row_dict["xg_away"],
        }
        # Usar história simplificada - para produção usaria deque real
        # Aqui delegamos compute_team_stats com dados da row
        # Para simplicidade, calculamos média manualmente usando os valores da row
        home_side = row_dict["home_team_id"] == team_id
        gf, ga = _window_values(hist_entry, feature)  # usa história construida
        gfs.append(gf)
        gas.append(ga)
    if not gfs:
        return {"gf_avg": 1.2, "ga_avg": 1.2}
    return {"gf_avg": round(sum(gfs) / len(gfs), 3),
            "ga_avg": round(sum(gas) / len(gas), 3)}


def _avg_stats_detail(league_id: int, team_id: int, window: int, feature: str,
                      as_of_timestamp: str | None = None) -> dict:
    """Jogos brutos que alimentaram as médias (auditoria do confronto)."""
    rows = _played_rows(
        "m.kickoff_datetime, th.name AS home, ta.name AS away, "
        "m.score_home, m.score_away, m.xg_home, m.xg_away, m.home_team_id",
        "AND (m.home_team_id=? OR m.away_team_id=?)",
        [league_id, team_id, team_id], window, as_of_timestamp)
    games = []
    for m in rows:
        row_dict = dict(m)
        home_side = row_dict["home_team_id"] == team_id
        hist_entry = {
            "gf": row_dict["score_home"] if home_side else row_dict["score_away"],
            "ga": row_dict["score_away"] if home_side else row_dict["score_home"],
            "xg_home": row_dict["xg_home"],
            "xg_away": row_dict["xg_away"],
        }
        gf, ga = _window_values(hist_entry, feature)
        games.append({
            "date": m["kickoff_datetime"][:10] if m["kickoff_datetime"] else None,
            "opponent": m["away"] if home_side else m["home"],
            "side": "casa" if home_side else "fora",
            "gf": gf,
            "ga": ga,
            "xg": m["xg_home"] if home_side else m["xg_away"],
            "xg_against": m["xg_away"] if home_side else m["xg_home"],
        })
    return {"games_used": games, "count": len(games)}


def _model_for(league_id: int) -> dict:
    return get_model(league_id)


def _recent_form(league_id: int, team_id: int, limit: int = 5,
                 as_of_timestamp: str | None = None) -> list[dict]:
    rows = _played_rows(
        "m.kickoff_datetime, m.score_home, m.score_away, m.status, "
        "m.home_team_id, m.away_team_id, th.name AS home, ta.name AS away",
        "AND (m.home_team_id=? OR m.away_team_id=?)",
        [league_id, team_id, team_id], limit, as_of_timestamp)
    out = []
    for r in rows:
        played_home = r["home_team_id"] == team_id
        gf = r["score_home"] if played_home else r["score_away"]
        ga = r["score_away"] if played_home else r["score_home"]
        out.append({
            "date": r["kickoff_datetime"][:10] if r["kickoff_datetime"] else None,
            "opponent": r["away"] if played_home else r["home"],
            "played_home": played_home,
            "gf": gf,
            "ga": ga,
            "result": "W" if gf > ga else ("D" if gf == ga else "L"),
        })
    return out


def _h2h(league_id: int, home_team_id: int, away_team_id: int, limit: int = 5,
         as_of_timestamp: str | None = None) -> list[dict]:
    rows = _played_rows(
        "m.kickoff_datetime, m.score_home, m.score_away, m.xg_home, m.xg_away, "
        "th.name AS home, ta.name AS away",
        "AND ((m.home_team_id=? AND m.away_team_id=?) "
        "OR (m.home_team_id=? AND m.away_team_id=?))",
        [league_id, home_team_id, away_team_id, away_team_id, home_team_id],
        limit, as_of_timestamp)
    return [dict(r) for r in rows]


def _team_card(league_id: int, team_id: int, name: str, stats: dict, feature: str,
               as_of_timestamp: str | None = None) -> dict:
    query = (
        "SELECT COUNT(*) c FROM matches "
        "WHERE league_id=? AND (home_team_id=? OR away_team_id=?) "
        "  AND status='played' AND score_home IS NOT NULL "
    )
    params = [league_id, team_id, team_id]
    if as_of_timestamp:
        query += " AND date(kickoff_datetime) < date(?)"
        params.append(as_of_timestamp)
    gp = db.run_query(query, tuple(params))[0]["c"] or 0
    return {
        "name": name,
        "gf_avg": stats.get("gf_avg", 0),
        "ga_avg": stats.get("ga_avg", 0),
        "feature": feature,
        "games": gp,
        "form": _recent_form(league_id, team_id, as_of_timestamp=as_of_timestamp),
    }


def _compare(league_id: int, home_id: int, away_id: int,
             home_name: str, away_name: str, home_stats: dict, away_stats: dict,
             feature: str, as_of_timestamp: str | None = None) -> dict:
    return {
        "home": _team_card(league_id, home_id, home_name, home_stats, feature, as_of_timestamp),
        "away": _team_card(league_id, away_id, away_name, away_stats, feature, as_of_timestamp),
        "h2h": _h2h(league_id, home_id, away_id, as_of_timestamp=as_of_timestamp),
    }


def _build(league_id: int, home_team_id: int, away_team_id: int,
           home_name: str, away_name: str, league_name: str,
           match: dict | None = None, as_of_timestamp: str | None = None) -> dict:
    model = _model_for(league_id)
    feature = model["feature"]
    window = model["window"]
    home_stats = _avg_stats(league_id, home_team_id, window, feature, as_of_timestamp)
    away_stats = _avg_stats(league_id, away_team_id, window, feature, as_of_timestamp)
    home_detail = _avg_stats_detail(league_id, home_team_id, window, feature, as_of_timestamp)
    away_detail = _avg_stats_detail(league_id, away_team_id, window, feature, as_of_timestamp)

    mi = MatchInput(
        league=league_name,
        home=TeamInput(name=home_name, **home_stats),
        away=TeamInput(name=away_name, **away_stats),
    )
    result = run_predict(mi, home_advantage=model["home_advantage"])

    base_match = {
        "id": None,
        "league": league_name,
        "league_id": league_id,
        "date": None,
        "kickoff": None,
        "home": home_name,
        "home_id": home_team_id,
        "away": away_name,
        "away_id": away_team_id,
    }
    if match:
        match = dict(match)
        # Derivar date de kickoff_datetime (YYYY-MM-DD) para compatibilidade
        kd = match.get("kickoff_datetime") or match.get("match_date")
        base_match.update({
            "id": match["id"],
            "date": kd[:10] if kd else None,
            "round": match.get("round"),
        })

    return {
        "match": base_match,
        "lambdas": result.lambdas,
        "probs": result.probs,
        "top_scores": result.top_scores,
        "proposals": result.proposals,
        "inputs": {"home": home_stats, "away": away_stats},
        "compare": _compare(league_id, home_team_id, away_team_id,
                            home_name, away_name, home_stats, away_stats, feature),
        "model": {"home_advantage": model["home_advantage"], "window": model["window"],
                  "feature": feature, "accuracy": model.get("accuracy"),
                  "brier": model.get("brier")},
        "data": {
            "source": f"sofascore_{feature}",
            "home": {"name": home_name, "avg": home_stats, **home_detail},
            "away": {"name": away_name, "avg": away_stats, **away_detail},
            "form": {"home": _recent_form(league_id, home_team_id),
                     "away": _recent_form(league_id, away_team_id)},
            "h2h": _h2h(league_id, home_team_id, away_team_id, limit=10),
            "model": {"home_advantage": model["home_advantage"], "window": model["window"],
                      "feature": feature, "accuracy": model.get("accuracy"),
                      "brier": model.get("brier")},
        },
    }


def predict_match(match_id: int, as_of_timestamp: str | None = None) -> dict:
    # O jogo previsto deve sempre ser encontrado; o filtro as-of aplica-se
    # apenas ao histórico usado nas features (dentro de _build).
    query = (
        "SELECT m.*, l.name AS league_name, th.name AS home_name, ta.name AS away_name "
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
    return _build(m["league_id"], m["home_team_id"], m["away_team_id"],
                  m["home_name"], m["away_name"], m["league_name"], m, as_of_timestamp)


def predict_league_upcoming(league_id: int, limit: int = 10,
                            as_of_timestamp: str | None = None) -> list[dict]:
    if as_of_timestamp:
        condition = "AND date(kickoff_datetime) < date(?)"
        params = (league_id, limit, as_of_timestamp)
    else:
        condition = ""
        params = (league_id, limit)
    
    query = (
        "SELECT id FROM matches WHERE league_id=? {condition} "
        "ORDER BY kickoff_datetime, id LIMIT ?"
    ).format(condition=condition)
    rows = db.run_query(query, params)
    return [predict_match(r["id"], as_of_timestamp) for r in rows]


def predict_fixture(league_id: int, home_team_id: int, away_team_id: int,
                    as_of_timestamp: str | None = None) -> dict:
    l = db.run_query("SELECT id, name, country FROM leagues WHERE id=?", (league_id,))[0]
    rows = db.run_query(
        "SELECT id, name FROM teams WHERE league_id=? AND id IN (?,?)",
        (league_id, home_team_id, away_team_id))
    names = {r["id"]: r["name"] for r in rows}
    if not names or home_team_id not in names or away_team_id not in names:
        raise IndexError("Confronto não encontrado")
    return _build(league_id, home_team_id, away_team_id,
                  names[home_team_id], names[away_team_id], l["name"],
                  as_of_timestamp=as_of_timestamp)