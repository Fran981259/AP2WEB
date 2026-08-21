"""EVOLUTION TRACKER — detecta mudanças reais nas métricas do sistema.

Uma evolução só é confirmada quando um métrica MEDIDO muda (delta ≠ 0)
em relação ao baseline armazenado. Nada de "parece melhor".

Uso:
  backend/.venv/bin/python -m app.evolution_tracker --check
  backend/.venv/bin/python -m app.evolution_tracker --baseline   # snapshot atual
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent / "data"
BASELINE_FILE = _DATA_DIR / "evolution_baseline.json"
HISTORY_FILE = _DATA_DIR / "evolution_history.jsonl"
API_HEALTH_URL = os.environ.get("AP2WEB_API_URL",
                                "http://localhost:8000/api/health")

# Métricas-chave que devem evoluir (todas walk-forward, as-of consistente)
LEAGUES_TO_TRACK = [20, 18, 65, 23, 24]  # top 5 por jogos jogados


def _snapshot(skip_regression: bool = False) -> dict:
    """Coleta métricas atuais do sistema.

    skip_regression: pula a suíte selenium (lenta); usado pelo endpoint da UI.
    """
    sys.path.insert(0, "backend")
    from app import db, learning
    from app.xgb_engine import compare_models

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


def _load_baseline() -> dict | None:
    if not os.path.exists(BASELINE_FILE):
        return None
    with open(BASELINE_FILE) as f:
        return json.load(f)


def _save_baseline(snap: dict):
    os.makedirs(os.path.dirname(BASELINE_FILE), exist_ok=True)
    with open(BASELINE_FILE, "w") as f:
        json.dump(snap, f, indent=2)


def _append_history(snap: dict):
    """Registro append-only: cada medição vira uma linha — nunca sobrescreve."""
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, "a") as f:
        f.write(json.dumps(snap) + "\n")


def _load_history(limit: int = 50) -> list[dict]:
    """Histórico cronológico de medições (mais recente por último)."""
    if not os.path.exists(HISTORY_FILE):
        return []
    rows = []
    with open(HISTORY_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue  # linha corrompida não derruba o histórico
    return rows[-limit:]


def _history_count() -> int:
    """Total de medições persistentes."""
    return len(_load_history(limit=10**9))


def _trend_series(history: list[dict]) -> dict:
    """Séries temporais por liga para plotar tendência (acc/brier)."""
    series: dict[str, list] = {}
    for snap in history:
        ts = (snap.get("timestamp") or "")[:16].replace("T", " ")
        for lid, m in (snap.get("leagues") or {}).items():
            if "error" in m:
                continue
            s = series.setdefault(lid, [])
            s.append({"x": len(s), "ts": ts,
                      "acc": m.get("poisson_accuracy"),
                      "brier": m.get("poisson_brier"),
                      "n": len(s)})
    return series


def _compare(current: dict, baseline: dict) -> list[dict]:
    """Retorna lista de mudanças detectadas (delta ≠ 0)."""
    changes = []

    # API health
    if current.get("api_health") != baseline.get("api_health"):
        changes.append({
            "metric": "api_health",
            "before": baseline.get("api_health"),
            "after": current.get("api_health"),
            "delta": "changed",
        })

    # Regression suite
    if current.get("regression_suite") != baseline.get("regression_suite"):
        changes.append({
            "metric": "regression_suite",
            "before": baseline.get("regression_suite"),
            "after": current.get("regression_suite"),
            "delta": "changed",
        })

    # Métricas por liga
    for lid, cur in current.get("leagues", {}).items():
        base = baseline.get("leagues", {}).get(lid)
        if not base or "error" in cur or "error" in base:
            continue
        for key in ("poisson_accuracy", "poisson_brier", "poisson_logloss"):
            if key in cur and key in base:
                delta = cur[key] - base[key]
                if abs(delta) > 1e-4:  # ignora ruído numérico
                    changes.append({
                        "metric": f"league_{lid}_{key}",
                        "before": base[key],
                        "after": cur[key],
                        "delta": round(delta, 4),
                    })

    return changes


def main():
    if "--baseline" in sys.argv:
        snap = _snapshot()
        _save_baseline(snap)
        _append_history(snap)
        print(f"Baseline salvo em {BASELINE_FILE} ({snap['timestamp']})")
        return

    baseline = _load_baseline()
    if not baseline:
        print("Nenhum baseline. Rode com --baseline primeiro.")
        sys.exit(1)

    current = _snapshot()
    changes = _compare(current, baseline)

    if not changes:
        print("✅ Nenhuma evolução detectada — sistema está estável.")
    else:
        print(f"⚡ {len(changes)} mudança(s) detectada(s):")
        for c in changes:
            print(f"  {c['metric']}: {c['before']} → {c['after']} (delta={c['delta']})")

    # Persiste a medição no histórico e atualiza o baseline
    _append_history(current)
    _save_baseline(current)


if __name__ == "__main__":
    main()