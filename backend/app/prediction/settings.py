"""Prediction settings: flags, version pins and logger."""
from __future__ import annotations

import logging
import os


USE_BAYESIAN: bool = os.environ.get("USE_BAYESIAN", "false").lower() == "true"
# Nota P3: global mantido por compatibilidade, mas comportamento determinístico deve usar
# parâmetro explícito `use_bayesian` em _build/predict_* (request-scoped). Ver _should_use_bayesian.

FEATURE_VERSION = "2.0_team_perspective_20260912"
MODEL_CODE_VERSION = "poisson_v4_canonical_dc_20260912"

_log = logging.getLogger("ap2web.prediction")
