"""System snapshot: API health, per-league metrics, regression suite."""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone

from .paths import API_HEALTH_URL, LEAGUES_TO_TRACK


def _snapshot(skip_regression: bool = False) -> dict:
    """Coleta métricas atuais do sistema.

    skip_regression: pula a suíte selenium (lenta); usado pelo endpoint da UI.
    """
    sys.path.insert(0, "backend")
    from app import learning

    snap = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "leagues": {},
        "api_health": None,
        "regression_suite": None,
    }

    # API health (ping local; no deploy, o próprio endpoint respondendo prova liveness)
    try:
        import requests
        r = requests.get(API_HEALTH_URL, timeout=5)
        snap["api_health"] = r.status_code == 200
    except Exception:
        snap["api_health"] = False

    # Métricas por liga (Poisson baseline)
    for lid in LEAGUES_TO_TRACK:
        try:
            bt = learning.backtest_league(lid)
            snap["leagues"][str(lid)] = {
                "poisson_accuracy": bt["accuracy"],
                "poisson_brier": bt["brier"],
                "poisson_logloss": bt.get("logloss", 1.0),
            }
        except Exception as e:
            snap["leagues"][str(lid)] = {"error": str(e)[:80]}

    # Regression suite
    if skip_regression:
        snap["regression_suite"] = None
    else:
        try:
            out = subprocess.run(
                [sys.executable, "tests/regression_suite.py"],
                capture_output=True, text=True, timeout=180)
            snap["regression_suite"] = "PASS" if "PASS" in out.stdout else "FAIL"
        except Exception:
            snap["regression_suite"] = "ERROR"

    return snap
