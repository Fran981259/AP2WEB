"""Serviço de previsão — aplica o motor Poisson (model.py) aos dados do Sofascore.

Alimenta lambdas com as médias de xG (ou gols) marcados/sofridos dos últimos N
jogos de cada time, usando a feature calibrada por liga (learning.get_model).

Integração Bayesian (FASE 13): opcional via USE_BAYESIAN=true
Substitui médias MLE por estimativas Gamma-Poisson posteriors.

Decomposto em submódulos temáticos; este pacote reexporta o API pública do
antigo módulo ``prediction``.
"""
from __future__ import annotations

from .bayesian import (
    _avg_stats_bayesian,
    _get_bayesian_engine,
    _match_gamma,
    _run_bayesian_predict,
    _should_use_bayesian,
    _with_posterior_means,
    invalidate_prediction_cache,
)
from .builder import _build, _model_for
from .context import _apply_context, _context_flags, _kickoff_ts
from .history import (
    _avg_stats,
    _avg_stats_detail,
    _compare,
    _h2h,
    _played_rows,
    _recent_form,
    _team_card,
)
from .service import predict_fixture, predict_league_upcoming, predict_match
from .settings import FEATURE_VERSION, MODEL_CODE_VERSION, USE_BAYESIAN

__all__ = [
    "FEATURE_VERSION",
    "MODEL_CODE_VERSION",
    "USE_BAYESIAN",
    "_apply_context",
    "_avg_stats",
    "_avg_stats_bayesian",
    "_avg_stats_detail",
    "_build",
    "_compare",
    "_context_flags",
    "_get_bayesian_engine",
    "_h2h",
    "_kickoff_ts",
    "_match_gamma",
    "_model_for",
    "_played_rows",
    "_recent_form",
    "_run_bayesian_predict",
    "_should_use_bayesian",
    "_team_card",
    "_with_posterior_means",
    "invalidate_prediction_cache",
    "predict_fixture",
    "predict_league_upcoming",
    "predict_match",
]
