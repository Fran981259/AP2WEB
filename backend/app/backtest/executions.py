"""Auditable execution lifecycle for backtest runs (snapshot, hash, finish)."""
from __future__ import annotations

import hashlib

from .. import execution_store
from ..learning import backtest_league
from ..scientific import build_snapshot_manifest
from .paths import logger


def _snapshot_metadata(league_id: int | None) -> tuple[dict, dict]:
    """Capture the immutable completed-match manifest without storing its full rows twice."""
    manifest = build_snapshot_manifest(league_id)
    return manifest, {key: value for key, value in manifest.items() if key != "matches"}


def _content_hash(value: dict) -> str:
    return hashlib.sha256(execution_store.canonical_json(value).encode("utf-8")).hexdigest()


def _finish_execution(execution_id: str, status: str, results: dict) -> None:
    """Record the terminal state without obscuring the backtest's original exception."""
    try:
        execution_store.finish(
            execution_id=execution_id,
            status=status,
            artifact_content_hash=_content_hash(results),
            results=results,
        )
    except Exception:
        logger.exception("could not finish backtest execution %s", execution_id)


def run_single_league_backtest(league_id: int) -> dict:
    """Run the legacy single-league backtest with an auditable execution lifecycle."""
    _manifest, snapshot = _snapshot_metadata(league_id)
    parameters = {
        "scope": "single_league",
        "league_id": league_id,
        # These are the existing backtest_league defaults used by this endpoint.
        "effective_parameters": {"home_adv": 1.15, "window": 10, "feature": "xg", "rho": 0.0},
    }
    execution = execution_store.start(
        execution_type="backtest", snapshot_hash=snapshot["hash"], parameters=parameters)
    try:
        result = backtest_league(league_id)
    except Exception as error:
        _finish_execution(execution["execution_id"], "failed", {
            "snapshot_manifest": snapshot,
            "error": str(error)[:2000],
        })
        raise
    _finish_execution(execution["execution_id"], "completed", {
        "snapshot_manifest": snapshot,
        "metrics": result,
        "results": result,
    })
    return result
