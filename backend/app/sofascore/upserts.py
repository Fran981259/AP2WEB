"""DB upserts: leagues, teams and matches (with stats retry)."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from .. import db
from .client import _extract_stats, _fetch
from .tables import _SOURCE_STATUS, _STAT_COLS

logger = logging.getLogger("ap2web.sofascore")


def _upsert_league(cfg: dict, season_id: int, season_name: str) -> int:
    """Cria/atualiza a liga no banco e retorna o league_id local."""
    rows = db.run_query("SELECT id FROM leagues WHERE sofascore_id=?", (cfg["id"],))
    if rows:
        league_id = rows[0]["id"]
        db.run_exec(
            "UPDATE leagues SET name=?, country=?, season_id=?, season_name=? WHERE id=?",
            (cfg["name"], cfg["country"], season_id, season_name, league_id))
        return league_id
    return db.run_exec(
        "INSERT INTO leagues(sofascore_id, name, country, season_id, season_name) VALUES(?,?,?,?,?)",
        (cfg["id"], cfg["name"], cfg["country"], season_id, season_name))
def _upsert_team(league_id: int, sofascore_id: int, name: str) -> int:
    rows = db.run_query(
        "SELECT id FROM teams WHERE league_id=? AND sofascore_id=?",
        (league_id, sofascore_id))
    if rows:
        return rows[0]["id"]
    return db.run_exec(
        "INSERT INTO teams(league_id, sofascore_id, name) VALUES(?,?,?)",
        (league_id, sofascore_id, name))
def _upsert_match(league_id: int, event: dict) -> bool:
    """Salva um evento do Sofascore. Retorna True se era novo (inserido).

    Jogos já existentes só são atualizados no placar/status (sem re-raspar stats),
    o que deixa re-syncs muito mais rápidos.
    """
    with db.transaction():
        inserted = _upsert_match_in_transaction(league_id, event)
        if _SOURCE_STATUS.get(event.get("status", {}).get("code")) == "played":
            from ..history import resolve_predictions_for_match

            match = db.run_query(
                "SELECT id FROM matches WHERE league_id=? AND sofascore_id=?",
                (league_id, event["id"]))
            if match:
                resolve_predictions_for_match(match[0]["id"])
        return inserted
def _upsert_match_in_transaction(league_id: int, event: dict) -> bool:
    """Upsert one match while the caller owns its transaction."""
    eid = event["id"]
    home = event["homeTeam"]
    away = event["awayTeam"]
    hs = event.get("homeScore", {})
    as_ = event.get("awayScore", {})
    source_status = _SOURCE_STATUS.get(event.get("status", {}).get("code"))
    if source_status is None:
        logger.warning("ignoring event with unsupported source status eid=%s", eid)
        return False
    played = source_status == "played"
    ts = event.get("startTimestamp")
    round_no = (event.get("roundInfo") or {}).get("round")

    koff = None
    if ts is not None:
        koff = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

    home_id = _upsert_team(league_id, home["id"], home["name"])
    away_id = _upsert_team(league_id, away["id"], away["name"])

    score_home = hs.get("current") if played else None
    score_away = as_.get("current") if played else None
    ingested_at = datetime.now(timezone.utc).isoformat()

    # jogo já existe? atualiza só o essencial e não re-raspar stats
    stat_columns = [f"{column}_{side}" for column in _STAT_COLS.values()
                    for side in ("home", "away")]
    exists = db.run_query(
        "SELECT id, kickoff_datetime, match_date, round, score_home, score_away, status, "
        + ", ".join(stat_columns)
        + " FROM matches WHERE league_id=? AND sofascore_id=?", (league_id, eid))
    if exists:
        existing = dict(exists[0])
        # Unknown source states are not a safe basis for changing a persisted match.
        status = existing["status"]
        if source_status == "played":
            status = "played"
        elif source_status == "scheduled" and existing["status"] != "played":
            status = "scheduled"
        match_kickoff = koff or existing["kickoff_datetime"]
        db.run_exec(
            "UPDATE matches SET home_team_id=?, away_team_id=?, kickoff_datetime=?, match_date=?, "
            "round=?, status=?, score_home=?, score_away=?, source_ingested_at=? WHERE id=?",
            (home_id, away_id, match_kickoff,
              match_kickoff[:10] if koff else existing["match_date"],
              round_no if round_no is not None else existing["round"], status,
              score_home if score_home is not None else existing["score_home"],
              score_away if score_away is not None else existing["score_away"], ingested_at,
              exists[0]["id"]))

        # Retry incomplete stats for every played sync, not just the status transition.
        if source_status == "played" and any(existing.get(column) is None for column in stat_columns):
            try:
                url = f"https://www.sofascore.com/api/v1/event/{eid}/statistics"
                st = _extract_stats(_fetch(url, Path(f"/tmp/sofa_ev_{eid}_postsync.json")))
                update_vals = {}
                for key, column in _STAT_COLS.items():
                    for side in ("home", "away"):
                        target = f"{column}_{side}"
                        value = (st.get(key) or {}).get(side)
                        if existing.get(target) is None and value is not None:
                            update_vals[target] = value
                if update_vals:
                    set_clause = ", ".join(f"{column}=?" for column in update_vals)
                    db.run_exec(f"UPDATE matches SET {set_clause} WHERE id=?",
                                tuple(update_vals.values()) + (exists[0]["id"],))
            except Exception as e:  # noqa: BLE001 -- upstream statistics endpoint
                logger.warning("post-sync stats fetch eid=%s err=%s", eid, e, exc_info=True)
        
        return False

    st = {}
    if played:
        try:
            url = f"https://www.sofascore.com/api/v1/event/{eid}/statistics"
            raw = _fetch(url, Path(f"/tmp/sofa_ev_{eid}.json"))
            st = _extract_stats(raw)
        except Exception:  # noqa: BLE001
            time.sleep(1)
            st = {}

    # kickoff_datetime: converter startTimestamp para UTC ISO 8601
    # BASE.md §314-344: timestamp completo deve ser armazenado, não apenas data
    koff = None
    if ts is not None:
        koff = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    # match_date mantido para compatibilidade (apenas a data)
    # extrair data de koff (ISO UTC) ou None
    date_str = koff[:10] if koff else None

    cols = ["league_id", "sofascore_id", "home_team_id", "away_team_id", "kickoff_datetime",
             "match_date", "round", "status", "score_home", "score_away", "source_ingested_at"]
    vals = [league_id, eid, home_id, away_id, koff, date_str, round_no,
            "played" if played else "scheduled", score_home, score_away, ingested_at]
    for key, col in _STAT_COLS.items():
        cols.append(f"{col}_home")
        cols.append(f"{col}_away")
        vals.append((st.get(key) or {}).get("home"))
        vals.append((st.get(key) or {}).get("away"))

    ph = ",".join("?" for _ in cols)
    upd = ",".join(f"{c}=excluded.{c}" for c in cols if c != "sofascore_id")

    cur = db.run_exec(
        f"INSERT INTO matches({','.join(cols)}) VALUES({ph}) "
        f"ON CONFLICT(league_id, sofascore_id) DO UPDATE SET {upd}",
        vals)
    return cur is not None and cur > 0
