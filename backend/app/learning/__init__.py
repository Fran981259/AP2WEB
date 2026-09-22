"""Aprendizado e calibração do motor Poisson + Dixon-Coles (fonte: Sofascore).

Cada liga tem:
  - home_advantage: fator de mando calibrado
  - window: janela deslizante ótima
  - feature: xG, gols ou blend
  - rho: parâmetro de dependência Dixon-Coles (0 = Poisson puro)

Calibração via BACKTEST HONESTO — para prever o jogo N, usamos apenas
os jogos 1..N-1 (sem vazamento de dados). Grid search otimiza Brier score
sobre (feature × window × home_advantage × rho).

Métricas:
  - Acurácia 1X2: % de jogos onde o favorito acertou o resultado.
  - Brier score: erro quadrático médio (0 = perfeito).
  - Log Loss: penalização por confiança incorreta.

Decomposto em submódulos temáticos; este pacote reexporta o API pública do
antigo módulo ``learning``.
"""
from __future__ import annotations

from .calibration import (
    calibrate_all,
    calibrate_league,
    calibration_status,
    get_model,
    model_status,
    motor_curve,
)
from .grids import (
    FEATURE_GRID,
    HOME_ADVANTAGE_GRID,
    MIN_SAMPLES,
    RHO_GRID,
    WINDOW_GRID,
    _PLAYED_COUNT,
)
from .walkforward import (
    _predict_probs,
    _team_lambdas,
    backtest_completed_matches,
    backtest_league,
    walkforward_validation,
)

__all__ = [
    "FEATURE_GRID",
    "HOME_ADVANTAGE_GRID",
    "MIN_SAMPLES",
    "RHO_GRID",
    "WINDOW_GRID",
    "_PLAYED_COUNT",
    "_predict_probs",
    "_team_lambdas",
    "backtest_completed_matches",
    "backtest_league",
    "calibrate_all",
    "calibrate_league",
    "calibration_status",
    "get_model",
    "model_status",
    "motor_curve",
    "walkforward_validation",
]
