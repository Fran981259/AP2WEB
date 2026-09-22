"""Calibration grids, sample floor and shared SQL fragment (pure data)."""
from __future__ import annotations


HOME_ADVANTAGE_GRID = [1.05, 1.10, 1.15, 1.20, 1.25, 1.30]
WINDOW_GRID = [5, 10, 15]
RHO_GRID = [0.0, -0.05, -0.10, -0.13, -0.15, -0.20]  # Dixon-Coles param

MIN_SAMPLES = 20  # mínimo de previsões por liga para calibrar
FEATURE_GRID = ["xg", "goals", "blend"]  # features disponíveis para calibração


_PLAYED_COUNT = (
    "(SELECT COUNT(*) FROM matches m WHERE m.league_id={alias}.id "
    "AND m.status='played' AND m.score_home IS NOT NULL AND m.score_away IS NOT NULL)"
)
