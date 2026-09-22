"""Season discovery: active season, rounds and fallback seasons."""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Callable

from .client import _fetch

logger = logging.getLogger("ap2web.sofascore")


def _latest_season(tournament_id: int, heartbeat: Callable[[], None] | None = None) -> tuple[int, str] | None:
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
        if heartbeat:
            heartbeat()
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
def _season_rounds(tid: int, season_id: int,
                   heartbeat: Callable[[], None] | None = None) -> tuple[list[int], bool]:
    """Números de rodadas da temporada, sem duplicatas (Copa tem 5 e 5 duplicados)."""
    try:
        if heartbeat:
            heartbeat()
        rounds_data = _fetch(
            f"https://www.sofascore.com/api/v1/unique-tournament/{tid}/season/{season_id}/rounds",
            Path(f"/tmp/sofa_rounds_{tid}_{season_id}.json"))
    except Exception:  # noqa: BLE001
        return [], True
    seen: set[int] = set()
    out: list[int] = []
    for r in rounds_data.get("rounds", []):
        n = r.get("round")
        if n is not None and n not in seen:
            seen.add(n)
            out.append(n)
    return out, False
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
