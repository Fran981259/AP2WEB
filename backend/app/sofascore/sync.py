"""League sync orchestration: rounds, knockouts and local sync."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

from .. import db
from ..leagues_config import load_leagues
from .client import _fetch
from .seasons import _latest_season, _older_seasons, _season_rounds
from .upserts import _upsert_league, _upsert_match


def _fetch_round_events(tid: int, season_id: int, rid: int,
                        heartbeat: Callable[[], None] | None = None) -> tuple[list[dict], bool]:
    """Return round events and whether both upstream attempts failed."""
    ev_url = f"https://www.sofascore.com/api/v1/unique-tournament/{tid}/season/{season_id}/events/round/{rid}"
    for attempt in (1, 2):
        if heartbeat:
            heartbeat()
        try:
            ev_data = _fetch(ev_url, Path(f"/tmp/sofa_round_{tid}_{season_id}_{rid}.json"))
            return ev_data.get("events", []), False
        except Exception:  # noqa: BLE001
            time.sleep(2 + attempt)
    return [], True
def _fetch_all_events(tid: int, season_id: int,
                      heartbeat: Callable[[], None] | None = None) -> tuple[list[dict], list[int]]:
    """Todos os eventos da temporada via paginação events/last (cobre fases de mata-mata).

    Retorna lista de eventos únicos (por id). Tolerante a falhas de página.
    """
    seen: dict[int, dict] = {}
    failed_pages = []
    for page in range(0, 40):
        if heartbeat:
            heartbeat()
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
            failed_pages.append(page)
            time.sleep(2)
            break
    return list(seen.values()), failed_pages
def sync_league(cfg: dict, heartbeat: Callable[[], None] | None = None) -> dict:
    """Sincroniza uma liga inteira (temporada ativa + rodadas + mata-mata + stats).

    Fontes: rodadas numeradas (liga) + paginação events/last (fases eliminatórias),
    deduplicadas por event id. Tolerante a falhas por rodada/página/jogo.
    """
    tid = cfg["id"]
    if heartbeat:
        heartbeat()
    season = _latest_season(tid, heartbeat=heartbeat)
    if not season:
        return {"ok": False, "error": "Sem temporada disponível"}
    season_id, season_name = season
    league_id = _upsert_league(cfg, season_id, season_name)

    candidates = [season] + _older_seasons(tid, season_id)
    failed_rounds: list[dict] = []
    failed_pages: list[dict] = []
    rounds_unavailable: list[int] = []
    for sid, sname in candidates:
        if heartbeat:
            heartbeat()
        rounds, rounds_failed = _season_rounds(tid, sid, heartbeat=heartbeat)
        if rounds_failed:
            rounds_unavailable.append(sid)

        events: dict[int, dict] = {}
        for rid in rounds:
            if heartbeat:
                heartbeat()
            round_events, failed = _fetch_round_events(tid, sid, rid, heartbeat=heartbeat)
            if failed:
                failed_rounds.append({"season_id": sid, "round": rid})
            for e in round_events:
                events[e["id"]] = e
            time.sleep(0.1)
        # mata-mata (fases que não aparecem nas rodadas numeradas)
        all_events, pages = _fetch_all_events(tid, sid, heartbeat=heartbeat)
        failed_pages.extend({"season_id": sid, "page": page} for page in pages)
        for e in all_events:
            events.setdefault(e["id"], e)

        if events:
            saved = 0
            for event in events.values():
                if heartbeat:
                    heartbeat()
                if _upsert_match(league_id, event):
                    saved += 1
                time.sleep(0.05)
            partial = bool(failed_rounds or failed_pages or rounds_unavailable)
            if not partial:
                db.run_exec("UPDATE leagues SET last_sync=datetime('now'), season_id=?, season_name=? WHERE id=?",
                            (sid, sname, league_id))
            return {"ok": not partial, "partial": partial, "league_id": league_id,
                    "matches_found": len(events), "matches_saved": saved, "season": sname,
                    "failed_rounds": failed_rounds, "failed_pages": failed_pages,
                    "rounds_unavailable": rounds_unavailable}

    partial = bool(failed_rounds or failed_pages or rounds_unavailable)
    return {"ok": False, "partial": partial, "error": "Nenhum evento nas temporadas recentes",
            "league_id": league_id, "failed_rounds": failed_rounds,
            "failed_pages": failed_pages, "rounds_unavailable": rounds_unavailable}
def sync_league_local(league_id: int, heartbeat: Callable[[], None] | None = None) -> dict:
    """Sincroniza uma liga do banco pelo id local (síncrono)."""
    row = db.run_query("SELECT sofascore_id FROM leagues WHERE id=?", (league_id,))
    if not row:
        raise IndexError("Liga não encontrada")
    sid = row[0]["sofascore_id"]
    cfg = next((c for c in load_leagues() if c["id"] == sid), None)
    if not cfg:
        raise IndexError("Liga sem configuração de sync")
    return sync_league(cfg, heartbeat=heartbeat)
