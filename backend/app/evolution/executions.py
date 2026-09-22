"""Measurement ledger: start/finish execution records for evaluations."""
from __future__ import annotations

import hashlib

from .. import execution_store
from .paths import LEAGUES_TO_TRACK, logger


def _content_hash(value: dict) -> str:
    return hashlib.sha256(execution_store.canonical_json(value).encode("utf-8")).hexdigest()


def _start_measurement_execution(*, skip_regression: bool, source: str) -> dict:
    """Start a ledger record without collecting metrics at import time."""
    parameters = {
        "source": source,
        "effective_parameters": {
            "skip_regression": skip_regression,
            "league_ids": LEAGUES_TO_TRACK,
        },
    }
    return execution_store.start(
        execution_type="evolution_measurement",
        snapshot_hash=_content_hash(parameters), parameters=parameters)
def _finish_measurement_execution(execution: dict, status: str, *, snapshot: dict | None = None,
                                  results: dict | None = None, error: str | None = None) -> None:
    """Finish a measurement record while preserving its original failure."""
    payload: dict = {"snapshot": snapshot} if snapshot is not None else {}
    if results is not None:
        payload["results"] = results
        payload["metrics"] = {
            "league_count": len(snapshot.get("leagues", {})) if snapshot else 0,
            "api_health": snapshot.get("api_health") if snapshot else None,
            "regression_suite": snapshot.get("regression_suite") if snapshot else None,
        }
    if error is not None:
        payload["error"] = error
    try:
        execution_store.finish(
            execution_id=execution["execution_id"], status=status,
            artifact_content_hash=_content_hash(payload), results=payload)
    except Exception:
        logger.exception("could not finish evolution execution %s", execution["execution_id"])
