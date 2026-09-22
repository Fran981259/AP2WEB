"""Shared paths, tracked leagues and logger for the evolution package."""
from __future__ import annotations

import logging
import os
from pathlib import Path

# NOTE: two levels up from this file == backend/app (same dir as before).
_DATA_DIR = Path(os.environ.get("AP2WEB_RUNTIME_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
_DATA_DIR.mkdir(parents=True, exist_ok=True)
BASELINE_FILE = _DATA_DIR / "evolution_baseline.json"
HISTORY_FILE = _DATA_DIR / "evolution_history.jsonl"
API_HEALTH_URL = os.environ.get("AP2WEB_API_URL",
                                 "http://localhost:8000/api/health")
logger = logging.getLogger("ap2web.evolution")

# Métricas-chave que devem evoluir (todas walk-forward, as-of consistente)
LEAGUES_TO_TRACK = [
    90, 18, 20, 65, 23, 24,   # top 6 por jogos (MLS, PL, Serie A, Argentina, Ligue 1, Buli)
    44, 41, 60,                # Brasil B/A/Copa
    82, 78, 14,                # Equador, Arg Copa, Uruguai
    85, 2, 59,                 # China Super, Finlândia, Brasil C
    91, 86, 8,                 # Chile, China League, Noruega 1Div
    80, 7, 94,                 # Coreia, Noruega Elite, Suécia
    4, 96, 67,                 # Irlanda, Paraguai, Libertadores
    84, 68, 61,                # Estônia, Sudamericana, Champions
    66, 73, 79, 9,             # Europa League, National League, México, Paraguai Clausura
]  # 31 ligas com >=30 jogos jogados
