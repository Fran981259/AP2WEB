from __future__ import annotations

import pytest

from backend.app import evolution as evolution_tracker
from backend.app import execution_store
from backend.app.evolution import paths as _evolution_paths
from backend.app.api import evolution


def test_evolution_endpoint_persists_measurement_and_legacy_history(monkeypatch, tmp_path):
    history_file = tmp_path / "evolution_history.jsonl"
    monkeypatch.setattr(_evolution_paths, "HISTORY_FILE", history_file)
    monkeypatch.setattr(evolution_tracker, "_snapshot", lambda skip_regression: {
        "timestamp": "2026-09-14T00:00:00+00:00",
        "leagues": {}, "api_health": False, "regression_suite": None,
    })
    monkeypatch.setattr(evolution_tracker, "_load_baseline", lambda: None)

    response = evolution.evolution_snapshot(user="tester")

    execution = execution_store.list(execution_type="evolution_measurement")[0]
    assert execution["status"] == "completed"
    assert execution["parameters"]["source"] == "endpoint"
    assert execution["parameters"]["effective_parameters"]["skip_regression"] is True
    assert execution["results"]["snapshot"] == response["current"]
    assert execution["results"]["metrics"]["league_count"] == 0
    assert evolution_tracker._load_history() == [response["current"]]


def test_evolution_endpoint_failure_gets_terminal_execution(monkeypatch):
    def fail(skip_regression):
        raise RuntimeError("measurement failed")

    monkeypatch.setattr(evolution_tracker, "_snapshot", fail)

    with pytest.raises(RuntimeError, match="measurement failed"):
        evolution.evolution_snapshot(user="tester")

    execution = execution_store.list(execution_type="evolution_measurement")[0]
    assert execution["status"] == "failed"
    assert execution["results"]["error"] == "measurement failed"
