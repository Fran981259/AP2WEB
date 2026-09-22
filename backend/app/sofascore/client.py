"""Upstream HTTP client: soccerdata handle, cached fetch, stat extraction."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from ..feature_engine import parse_stat_value as _parse_score
from .tables import _STAT_NAME_TO_COL

logger = logging.getLogger("ap2web.sofascore")


def _client():
    """Instância do soccerdata.Sofascore (mecanismo de HTTP com TLS impersonation)."""
    # Import lazily: soccerdata configures filesystem logging at import time.
    # API startup and tests should not require the scraper's external runtime.
    os.environ.setdefault(
        "SOCCERDATA_DIR",
        os.environ.get("AP2WEB_RUNTIME_DATA_DIR", "/tmp/ap2web-runtime"),
    )
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
