"""Sofascore → SQLite — fonte única de dados do AP2WEB.

Puxa para cada liga configurada: temporada ativa, todas as rodadas (resultados
e calendário) e estatísticas completas de cada jogo (xG, posse, chutes, passes,
escanteios, cartões, ...). Salva direto no banco SQLite.

Usa o mecanismo de HTTP do soccerdata (TLS impersonation → evita 403/CAPTCHA).
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from . import db
from .feature_engine import parse_stat_value as _parse_score
from .leagues_config import load_leagues

logger = logging.getLogger("ap2web.sofascore")

# Mapeamento de nomes de estatísticas do Sofascore → colunas internas do banco
# Construído a partir de _STAT_COLS para garantir consistência
_STAT_NAME_TO_COL = {
    "Ball possession": "possession",
    "Expected goals": "xg",
    "Expected goals on target": "xg_on_target",
    "Total shots": "shots_total",
    "Shots on target": "shots_on_target",
    "Shots off target": "shots_off_target",
    "Shots inside box": "shots_inside_box",
    "Shots outside box": "shots_outside_box",
    "Blocked shots": "blocked_shots",
    "Big chances": "big_chances",
    "Big chances missed": "big_chances_missed",
    "Corner kicks": "corners",
    "Fouls": "fouls",
    "Yellow cards": "yellow_cards",
    "Red cards": "red_cards",
    "Passes": "passes",
    "Accurate passes": "accurate_passes",
    "Offsides": "offsides",
    "Total saves": "saves",
    "Interceptions": "interceptions",
    "Recoveries": "recoveries",
    "Total tackles": "tackles",
    "Dribbles": "dribbles_won",
    "Duels": "duels_won",
    "Aerial duels": "aerial_duels_won",
    "Final third entries": "final_third",
    "Throw-ins": "throw_ins",
    "Goal kicks": "goal_kicks",
}


# Colunas do banco ↔ campos do JSON de statistics do Sofascore
_STAT_COLS = {
    "possession": "possession",
    "xg": "xg",
    "xg_on_target": "xg_on_target",
    "shots_total": "shots_total",
    "shots_on_target": "shots_on_target",
    "shots_off_target": "shots_off_target",
    "shots_inside_box": "shots_inside_box",
    "shots_outside_box": "shots_outside_box",
    "blocked_shots": "blocked_shots",
    "big_chances": "big_chances",
    "big_chances_missed": "big_chances_missed",
    "corners": "corners",
    "fouls": "fouls",
    "yellow_cards": "yellow_cards",
    "red_cards": "red_cards",
    "passes": "passes",
    "accurate_passes": "accurate_passes",
    "offsides": "offsides",
    "saves": "saves",
    "interceptions": "interceptions",
    "recoveries": "recoveries",
    "tackles": "tackles",
    "dribbles_won": "dribbles",
    "duels_won": "duels",
    "aerial_duels_won": "aerial_duels",
    "final_third_entries": "final_third",
    "throw_ins": "throw_ins",
    "goal_kicks": "goal_kicks",
}


def _client():
    """Instância do soccerdata.Sofascore (mecanismo de HTTP com TLS impersonation)."""
    # Import lazily: soccerdata configures filesystem logging at import time.
    # API startup and tests should not require the scraper's external runtime.
    import soccerdata as sd
    return sd.Sofascore(leagues="ENG-Premier League", seasons="2026")


def _fetch(url: str, cache: Path):
    reader = _client().get(url, cache)
    return json.load(reader)


def _extract_stats(raw: dict) -> dict:
    """Extrai as estatísticas home/away do payload de statistics."""
    out = {}
    for group in raw.get("statistics", []):
        for item in group.get("groups", []):
            for s in item.get("statisticsItems", []):
                name = (s.get("name") or "").strip()
                col_name = _STAT_NAME_TO_COL.get(name)
                if col_name:
                    out.setdefault(col_name, {
                        "home": _parse_score(s.get("home")),
                        "away": _parse_score(s.get("away"))
                    })
    return out


def _latest_season(tournament_id: int) -> tuple[int, str] | None:
    """Retorna (season_id, nome) da temporada ativa.

    Sofascore lista a temporada mais nova primeiro. Uma temporada recém-criada
    tem rodadas (calendário) mas nenhum resultado — o que inutiliza features e
    previsões. Preferência: primeira temporada com jogos já jogados; fallback
    para a primeira com rodadas; por último, a mais nova.
    """
    url = f"https://www.sofascore.com/api/v1/unique-tournament/{tournament_id}/seasons"
    data = _fetch(url, Path(f"/tmp/sofa_seasons_{tournament_id}.json"))
    seasons = data.get("seasons", [])
    fallback: tuple[int, str] | None = None
    for s in seasons[:4]:
        sid = s.get("id")
        if not sid:
            continue
        try:
            rounds_data = _fetch(
                f"https://www.sofascore.com/api/v1/unique-tournament/{tournament_id}/season/{sid}/rounds",
                Path(f"/tmp/sofa_rounds_{tournament_id}_{sid}.json"))
        except (OSError, ValueError, KeyError, Exception) as e:  # noqa: BLE001 — network upstream, log explicitly
            logger.warning("rounds fetch failed tid=%s sid=%s err=%s", tournament_id, sid, e)
            time.sleep(1)
            continue
        if not rounds_data.get("rounds"):
            continue
        if fallback is None:
            fallback = (sid, s.get("name"))
        # temporada com resultados? (página 0 de events/last = jogos mais recentes)
        try:
            ev_data = _fetch(
                f"https://www.sofascore.com/api/v1/unique-tournament/{tournament_id}/season/{sid}/events/last/0",
                Path(f"/tmp/sofa_last_check_{tournament_id}_{sid}.json"))
            played = any(
                (e.get("status") or {}).get("code") == 100
                for e in ev_data.get("events", []))
        except (OSError, ValueError, KeyError, Exception) as e:  # noqa: BLE001
            logger.debug("events/last check failed sid=%s err=%s", sid, e)
            played = False
        if played:
            return sid, s.get("name")
    return fallback


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
    eid = event["id"]
    home = event["homeTeam"]
    away = event["awayTeam"]
    hs = event.get("homeScore", {})
    as_ = event.get("awayScore", {})
    status_code = event.get("status", {}).get("code")
    played = status_code == 100
    ts = event.get("startTimestamp")
    round_no = (event.get("roundInfo") or {}).get("round")

    koff = None
    if ts is not None:
        koff = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

    home_id = _upsert_team(league_id, home["id"], home["name"])
    away_id = _upsert_team(league_id, away["id"], away["name"])

    score_home = hs.get("current") if played else None
    score_away = as_.get("current") if played else None

    # jogo já existe? atualiza só o essencial e não re-raspar stats
    exists = db.run_query(
        "SELECT id, xg_home, score_home, score_away, status FROM matches WHERE league_id=? AND sofascore_id=?",
        (league_id, eid))
    if exists:
        existing = dict(exists[0])
        # Verificar se status mudou de scheduled para played
        prev_status = existing.get("status")
        now_played = played

        # Atualizar placar e status
        db.run_exec(
            "UPDATE matches SET home_team_id=?, away_team_id=?, kickoff_datetime=?, round=?, "
            "status=?, score_home=?, score_away=? WHERE id=?",
            (home_id, away_id, koff if koff else existing.get("kickoff_datetime"), round_no,
             "played" if played else "scheduled",
             score_home, score_away, exists[0]["id"]))
        
        # Fluxo FASE 2: Se jogo terminou e stats ainda não foram coletadas completamente
        if now_played and prev_status != "played":
            # Verificar quais stats estão faltando
            missing_stats = []
            if existing.get("xg_home") is None or existing.get("xg_away") is None:
                missing_stats.append("xG")
            if not existing.get("possession_home") or not existing.get("possession_away"):
                missing_stats.append("possession")
            # Adicionar outras features conforme necessário...
            
            if missing_stats:
                # Coletar stats agora que jogo está finalizado
                try:
                    url = f"https://www.sofascore.com/api/v1/event/{eid}/statistics"
                    raw = _fetch(url, Path(f"/tmp/sofa_ev_{eid}_postsync.json"))
                    st = _extract_stats(raw)
                    # Update columns directly. This path handles a match that
                    # was scheduled at first sync and later becomes played.
                    update_vals = {}
                    for key, column in _STAT_COLS.items():
                        home_col, away_col = f"{column}_home", f"{column}_away"
                        if key in st and (existing.get(home_col) is None or existing.get(away_col) is None):
                            if existing.get(home_col) is None:
                                update_vals[home_col] = st[key].get("home")
                            if existing.get(away_col) is None:
                                update_vals[away_col] = st[key].get("away")
                    
                    if update_vals:
                        set_clause = ", ".join(f"{column}=?" for column in update_vals)
                        db.run_exec(
                            f"UPDATE matches SET {set_clause} WHERE id=?",
                            tuple(update_vals.values()) + (exists[0]["id"],))
                except (OSError, ValueError, KeyError, Exception) as e:  # noqa: BLE001
                    logger.warning("post-sync stats fetch eid=%s err=%s", eid, e, exc_info=True)
                    pass
        
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
            "match_date", "round", "status", "score_home", "score_away"]
    vals = [league_id, eid, home_id, away_id, koff, date_str, round_no,
            "played" if played else "scheduled", score_home, score_away]
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


def _fetch_round_events(tid: int, season_id: int, rid: int) -> list[dict]:
    """Eventos de uma rodada. Tolerante a 404/403: retorna [] em vez de abortar."""
    ev_url = f"https://www.sofascore.com/api/v1/unique-tournament/{tid}/season/{season_id}/events/round/{rid}"
    for attempt in (1, 2):
        try:
            ev_data = _fetch(ev_url, Path(f"/tmp/sofa_round_{tid}_{season_id}_{rid}.json"))
            return ev_data.get("events", [])
        except Exception:  # noqa: BLE001
            time.sleep(2 + attempt)
    return []


def _fetch_all_events(tid: int, season_id: int) -> list[dict]:
    """Todos os eventos da temporada via paginação events/last (cobre fases de mata-mata).

    Retorna lista de eventos únicos (por id). Tolerante a falhas de página.
    """
    seen: dict[int, dict] = {}
    for page in range(0, 40):
        try:
            url = (f"https://www.sofascore.com/api/v1/unique-tournament/{tid}/season/"
                   f"{season_id}/events/last/{page}")
            ev_data = _fetch(url, Path(f"/tmp/sofa_last_{tid}_{season_id}_{page}.json"))
            events = ev_data.get("events", [])
            if not events:
                break
            for e in events:
                seen[e["id"]] = e
            if not ev_data.get("hasNextPage"):
                break
        except Exception:  # noqa: BLE001
            time.sleep(2)
            break
    return list(seen.values())


def _season_rounds(tid: int, season_id: int) -> list[int]:
    """Números de rodadas da temporada, sem duplicatas (Copa tem 5 e 5 duplicados)."""
    try:
        rounds_data = _fetch(
            f"https://www.sofascore.com/api/v1/unique-tournament/{tid}/season/{season_id}/rounds",
            Path(f"/tmp/sofa_rounds_{tid}_{season_id}.json"))
    except Exception:  # noqa: BLE001
        return []
    seen: set[int] = set()
    out: list[int] = []
    for r in rounds_data.get("rounds", []):
        n = r.get("round")
        if n is not None and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def sync_league(cfg: dict) -> dict:
    """Sincroniza uma liga inteira (temporada ativa + rodadas + mata-mata + stats).

    Fontes: rodadas numeradas (liga) + paginação events/last (fases eliminatórias),
    deduplicadas por event id. Tolerante a falhas por rodada/página/jogo.
    """
    tid = cfg["id"]
    season = _latest_season(tid)
    if not season:
        return {"ok": False, "error": "Sem temporada disponível"}
    season_id, season_name = season
    league_id = _upsert_league(cfg, season_id, season_name)

    candidates = [season] + _older_seasons(tid, season_id)
    for sid, sname in candidates:
        rounds = _season_rounds(tid, sid)

        events: dict[int, dict] = {}
        skipped = []
        for rid in rounds:
            for e in _fetch_round_events(tid, sid, rid):
                events[e["id"]] = e
            time.sleep(0.1)
        # mata-mata (fases que não aparecem nas rodadas numeradas)
        for e in _fetch_all_events(tid, sid):
            events.setdefault(e["id"], e)

        if events:
            saved = 0
            for event in events.values():
                if _upsert_match(league_id, event):
                    saved += 1
                time.sleep(0.05)
            db.run_exec("UPDATE leagues SET last_sync=datetime('now'), season_id=?, season_name=? WHERE id=?",
                        (sid, sname, league_id))
            return {"ok": True, "league_id": league_id, "matches_found": len(events),
                    "matches_saved": saved, "season": sname, "skipped_rounds": skipped}

    return {"ok": False, "error": "Nenhum evento nas temporadas recentes",
            "league_id": league_id}


def _older_seasons(tid: int, current_season_id: int) -> list[tuple[int, str]]:
    """Temporadas anteriores à atual (para fallback quando a atual não tem jogos)."""
    data = _fetch(f"https://www.sofascore.com/api/v1/unique-tournament/{tid}/seasons",
                  Path(f"/tmp/sofa_seasons_{tid}.json"))
    out = []
    for s in data.get("seasons", [])[1:4]:
        sid = s.get("id")
        if sid and sid != current_season_id:
            out.append((sid, s.get("name")))
    return out


def sync_league_local(league_id: int) -> dict:
    """Sincroniza uma liga do banco pelo id local (síncrono)."""
    row = db.run_query("SELECT sofascore_id FROM leagues WHERE id=?", (league_id,))
    if not row:
        raise IndexError("Liga não encontrada")
    sid = row[0]["sofascore_id"]
    cfg = next((c for c in load_leagues() if c["id"] == sid), None)
    if not cfg:
        raise IndexError("Liga sem configuração de sync")
    return sync_league(cfg)


def status() -> dict:
    """Read-only compatibility status backed by the durable jobs table.

    No thread/daemon state is used. Contract keys kept for old callers.
    """
    from . import jobs

    recent = jobs.list_jobs(limit=10, job_type="sync_all")
    recent.extend(jobs.list_jobs(limit=10, job_type="sync_league"))
    recent.sort(key=lambda j: j.get("id", 0), reverse=True)
    active = [j for j in recent if j.get("status") in ("pending", "running")]
    completed = [j for j in recent if j.get("status") == "completed"]
    total = max(len(recent), 1)
    last = recent[0] if recent else None
    return {
        "running": bool(active),
        "done": len(completed),
        "total": total,
        "current": active[0].get("parameters", "") if active else "",
        "ok": len(completed),
        "fail": sum(1 for j in recent if j.get("status") == "failed"),
        "errors": [{"job_id": j["id"], "error": j.get("error_message")}
                   for j in recent if j.get("status") == "failed"],
        "finished_at": last.get("finished_at") if last else None,
        "error": last.get("error_message") if last and last.get("status") == "failed" else None,
    }


def dataset(league_id: int | None = None, limit: int = 2000,
            next_round: bool = False) -> list[dict]:
    """Lista os jogos (com stats) do banco, opcionalmente filtrado por liga.

    `next_round=True` → apenas a próxima rodada agendada de cada liga
    (menor round com jogos futuros; por isso a seleção é por liga).
    """
    q = ("SELECT m.*, th.name AS home, ta.name AS away, l.name AS league_name "
         "FROM matches m "
         "JOIN teams th ON th.id=m.home_team_id "
         "JOIN teams ta ON ta.id=m.away_team_id "
         "JOIN leagues l ON l.id=m.league_id ")
    conds: list[str] = []
    params: list = []
    if league_id:
        conds.append("m.league_id=?")
        params.append(league_id)
    if next_round:
        conds.append("m.kickoff_datetime >= datetime('now')")
        conds.append(
            "m.round = (SELECT MIN(m2.round) FROM matches m2 "
            "WHERE m2.league_id=m.league_id AND m2.status='scheduled' "
            "AND m2.kickoff_datetime >= datetime('now') "
            "AND m2.round IS NOT NULL)")
    if conds:
        q += "WHERE " + " AND ".join(conds) + " "
    q += "ORDER BY m.kickoff_datetime {}, m.id LIMIT ?".format(
        "ASC" if next_round else "DESC")
    params.append(limit)
    return [dict(r) for r in db.run_query(q, tuple(params))]


def leagues() -> list[dict]:
    """Ligas no banco com contagem de jogos."""
    return [dict(r) for r in db.run_query(
        "SELECT l.*, "
        " (SELECT COUNT(*) FROM matches m WHERE m.league_id=l.id AND m.status='played') AS played, "
        " (SELECT COUNT(*) FROM matches m WHERE m.league_id=l.id AND m.status='scheduled') AS scheduled "
        "FROM leagues l ORDER BY l.name")]
