"""Sofascore → SQLite — fonte única de dados do AP2WEB.

Puxa para cada liga configurada: temporada ativa, todas as rodadas (resultados
e calendário) e estatísticas completas de cada jogo (xG, posse, chutes, passes,
escanteios, cartões, ...). Salva direto no banco SQLite.

Usa o mecanismo de HTTP do soccerdata (TLS impersonation → evita 403/CAPTCHA).

Decomposto em submódulos temáticos; este pacote reexporta o API pública do
antigo módulo ``sofascore_data`` (incluindo ``load_leagues``, importado aqui
de ``leagues_config`` para preservar o ponto de monkeypatch dos testes).
"""
from __future__ import annotations

from ..leagues_config import load_leagues
from .client import _client, _extract_stats, _fetch
from .queries import dataset, leagues, status
from .seasons import _latest_season, _older_seasons, _season_rounds
from .sync import (
    _fetch_all_events,
    _fetch_round_events,
    sync_league,
    sync_league_local,
)
from .tables import _SOURCE_STATUS, _STAT_COLS, _STAT_NAME_TO_COL
from .upserts import (
    _upsert_league,
    _upsert_match,
    _upsert_match_in_transaction,
    _upsert_team,
)

__all__ = [
    "_SOURCE_STATUS",
    "_STAT_COLS",
    "_STAT_NAME_TO_COL",
    "_client",
    "_extract_stats",
    "_fetch",
    "_fetch_all_events",
    "_fetch_round_events",
    "_latest_season",
    "_older_seasons",
    "_season_rounds",
    "_upsert_league",
    "_upsert_match",
    "_upsert_match_in_transaction",
    "_upsert_team",
    "dataset",
    "leagues",
    "load_leagues",
    "status",
    "sync_league",
    "sync_league_local",
]
