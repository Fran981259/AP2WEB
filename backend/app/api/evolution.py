"""Evolution tracker routes: metric snapshots and historical trend."""
from __future__ import annotations

from fastapi import Depends
from fastapi.routing import APIRouter

from .. import db, config
from ..auth import current_user
from .deps import clamp_limit

settings = config.settings
router = APIRouter()


@router.get("/api/evolution/snapshot", tags=["evolution"])
def evolution_snapshot(user: str = Depends(current_user)):
    from ..evolution import (_append_history, _compare, _evolution_pct,
                                _finish_measurement_execution, _history_count,
                                _load_baseline, _load_history, _snapshot,
                                _start_measurement_execution)
    execution = _start_measurement_execution(skip_regression=True, source="endpoint")
    try:
        current = _snapshot(skip_regression=True)
        baseline = _load_baseline()
        current["api_health"] = True
        current["regression_suite"] = baseline.get("regression_suite") if baseline else None
        changes = _compare(current, baseline) if baseline else []
        history = _load_history(limit=10**9)
        evolution = _evolution_pct(current, history) if history else {}

        if current.get("leagues"):
            league_ids = [int(lid) for lid in current["leagues"].keys()]
            placeholders = ",".join("?" for _ in league_ids)
            league_names = db.run_query(
                f"SELECT id, name FROM leagues WHERE id IN ({placeholders})",
                tuple(league_ids))
            name_map = {str(r["id"]): r["name"] for r in league_names}
            for lid, m in current["leagues"].items():
                m["league_name"] = name_map.get(lid, f"Liga {lid}")

        _append_history(current)
    except Exception as error:
        _finish_measurement_execution(execution, "failed", error=str(error)[:2000])
        raise
    history_size = _history_count()
    _finish_measurement_execution(execution, "completed", snapshot=current, results={
        "changes": changes,
        "evolution": evolution,
        "history_size": history_size,
    })
    return {
        "current": current,
        "baseline": baseline,
        "changes": changes,
        "evolution": evolution,
        "stable": len(changes) == 0,
        "history_size": history_size,
        "env": "dev" if settings.env != "production" else "deploy",
    }


@router.get("/api/evolution/history", tags=["evolution"])
def evolution_history(limit: int = 50, user: str = Depends(current_user)):
    from ..evolution import _load_history, _trend_series
    history = _load_history(clamp_limit(limit, 500))
    return {
        "count": len(history),
        "history": history,
        "series": _trend_series(history),
    }
