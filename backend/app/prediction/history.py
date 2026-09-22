"""Team history queries: played rows, averages, form, h2h, compare cards."""
from __future__ import annotations

from .. import db
from ..feature_engine import team_match_stats, window_stats


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
        "AND m.score_away IS NOT NULL "
        f"{extra_where} "
    )
    all_params = list(params)
    if as_of_timestamp:
        query += "AND datetime(m.kickoff_datetime) < datetime(?) "
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
    return window_stats([dict(r) for r in rows], team_id, window, feature)
def _avg_stats_detail(league_id: int, team_id: int, window: int, feature: str,
                      as_of_timestamp: str | None = None) -> dict:
    """Jogos brutos que alimentaram as médias (auditoria do confronto)."""
    rows = _played_rows(
        "m.kickoff_datetime, th.name AS home, ta.name AS away, "
        "m.score_home, m.score_away, m.xg_home, m.xg_away, m.home_team_id, m.away_team_id",
        "AND (m.home_team_id=? OR m.away_team_id=?)",
        [league_id, team_id, team_id], window, as_of_timestamp)
    games = []
    for m in rows:
        row_dict = dict(m)
        home_side = row_dict["home_team_id"] == team_id
        selected = team_match_stats(row_dict, team_id, feature)
        gf, ga = selected["gf"], selected["ga"]
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
        query += " AND datetime(kickoff_datetime) < datetime(?)"
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
