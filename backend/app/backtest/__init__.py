"""Backtest Engine — ciclos síncronos consumidos pelo worker de jobs.

Componentes:
  1. temporal: cross-validation temporal K-fold (zero leakage)
  2. meta: MetaLearner com sugestões heurísticas baseadas no histórico
  3. state/cycle/detailed: BacktestLoop decomposto em mixins temáticos
  4. executions: lifecycle auditável (snapshot, hash, finish) + single-league
  5. loop: composição final + singleton

Fluxo por ciclo:
  1. Para cada liga com dados suficientes:
     a. Roda walk-forward backtest (learning.backtest_league)
     b. Roda TemporalCV para validação robusta
     c. Alimenta MetaLearner com métricas
  2. MetaLearner sugere novos hiperparâmetros
  3. Roda calibrate_league com grid expandido
  4. Compara métricas antes/depois
  5. Promove ou reverte parâmetros
  6. Persiste resultado no evolution_tracker

Os nomes reexportados abaixo preservam o API pública do antigo módulo
``backtest_engine`` (incluindo os pontos de monkeypatch usados em testes).
"""
from __future__ import annotations

from ..learning import backtest_league, get_model
from ..scientific import build_snapshot_manifest
from .executions import (
    _content_hash,
    _finish_execution,
    _snapshot_metadata,
    run_single_league_backtest,
)
from .loop import BacktestLoop, get_loop
from .meta import MetaLearner
from .paths import _HISTORY_FILE, _STATE_FILE
from .temporal import run_temporal_cv, temporal_cv

__all__ = [
    "BacktestLoop",
    "MetaLearner",
    "_HISTORY_FILE",
    "_STATE_FILE",
    "_content_hash",
    "_finish_execution",
    "_snapshot_metadata",
    "backtest_league",
    "build_snapshot_manifest",
    "get_loop",
    "get_model",
    "run_single_league_backtest",
    "run_temporal_cv",
    "temporal_cv",
]
