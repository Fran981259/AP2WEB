"""Trend analysis: series, baseline comparison, evolution percent."""
from __future__ import annotations


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
def _evolution_pct(current: dict, history: list[dict]) -> dict:
    """Calcula % de evolução desde a primeira medição até agora.

    Retorna dict[lid][metric] = {first, current, pct}.
    Acurácia: quanto maior melhor (+% = evolução).
    Brier/LogLoss: quanto menor melhor (-% = evolução).
    """
    if not history:
        return {}
    first = history[0]
    result = {}
    for lid, cur in current.get("leagues", {}).items():
        if "error" in cur:
            continue
        first_league = first.get("leagues", {}).get(lid, {})
        if not first_league or "error" in first_league:
            continue
        result[lid] = {}
        for key in ("poisson_accuracy", "poisson_brier", "poisson_logloss"):
            f_val = first_league.get(key)
            c_val = cur.get(key)
            if f_val is None or c_val is None or f_val == 0:
                continue
            pct = round((c_val - f_val) / abs(f_val) * 100, 2)
            result[lid][key] = {"first": f_val, "current": c_val, "pct": pct}
    return result
