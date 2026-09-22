"""EVOLUTION TRACKER — detecta mudanças reais nas métricas do sistema.

Uma evolução só é confirmada quando um métrica MEDIDO muda (delta ≠ 0)
em relação ao baseline armazenado. Nada de "parece melhor".

Uso:
  backend/.venv/bin/python -m app.evolution_tracker --check
  backend/.venv/bin/python -m app.evolution_tracker --baseline   # snapshot atual

Decomposto em submódulos temáticos; este pacote reexporta o API pública do
antigo módulo ``evolution_tracker``. Caminhos de arquivo vivem em
``evolution.paths`` — testes fazem monkeypatch de ``paths.HISTORY_FILE``.
"""
from __future__ import annotations

from .analysis import _compare, _evolution_pct, _trend_series
from .cli import main
from .executions import (
    _content_hash,
    _finish_measurement_execution,
    _start_measurement_execution,
)
from .history import (
    _append_history,
    _history_count,
    _load_baseline,
    _load_history,
    _save_baseline,
)
from .measure import _snapshot
from .paths import BASELINE_FILE, HISTORY_FILE, LEAGUES_TO_TRACK

__all__ = [
    "BASELINE_FILE",
    "HISTORY_FILE",
    "LEAGUES_TO_TRACK",
    "_append_history",
    "_compare",
    "_content_hash",
    "_evolution_pct",
    "_finish_measurement_execution",
    "_history_count",
    "_load_baseline",
    "_load_history",
    "_save_baseline",
    "_snapshot",
    "_start_measurement_execution",
    "_trend_series",
    "main",
]
