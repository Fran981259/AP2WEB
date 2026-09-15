from __future__ import annotations

import pytest

from backend.app import backtest_engine, db, execution_store


def _manifest(league_id):
    return {
        "league_id": league_id,
        "completed_match_count": 3,
        "usable_match_count": 3,
        "matches": [],
        "hash": f"snapshot-{league_id}",
    }


def test_single_league_backtest_persists_one_completed_execution(monkeypatch):
    monkeypatch.setattr(backtest_engine, "build_snapshot_manifest", _manifest)
    expected = {"accuracy": 50.0, "brier": 0.4, "total": 3}
    monkeypatch.setattr(backtest_engine, "backtest_league", lambda league_id: expected)

    assert backtest_engine.run_single_league_backtest(7) == expected

    execution = execution_store.list(execution_type="backtest")[0]
    assert execution["status"] == "completed"
    assert execution["snapshot_hash"] == "snapshot-7"
    assert execution["parameters"]["effective_parameters"]["window"] == 10
    assert execution["results"]["snapshot_manifest"]["hash"] == "snapshot-7"
    assert execution["results"]["metrics"] == expected
    rows = db.run_query("SELECT event_type FROM execution_events WHERE execution_id=?",
                        (execution["execution_id"],))
    assert [row["event_type"] for row in rows] == ["started", "finished"]


def test_single_league_backtest_failure_gets_terminal_execution(monkeypatch):
    monkeypatch.setattr(backtest_engine, "build_snapshot_manifest", _manifest)

    def fail(league_id):
        raise RuntimeError("walk-forward failed")

    monkeypatch.setattr(backtest_engine, "backtest_league", fail)

    with pytest.raises(RuntimeError, match="walk-forward failed"):
        backtest_engine.run_single_league_backtest(8)

    execution = execution_store.list(execution_type="backtest")[0]
    assert execution["status"] == "failed"
    assert execution["results"]["error"] == "walk-forward failed"


def test_temporal_cv_persists_completed_execution(monkeypatch):
    monkeypatch.setattr(backtest_engine, "build_snapshot_manifest", _manifest)
    expected = {
        "folds": [], "mean_accuracy": 51.5, "mean_brier": 0.31,
        "std_accuracy": 1.0, "std_brier": 0.02, "total_matches": 30, "n_folds": 4,
    }
    monkeypatch.setattr(backtest_engine, "temporal_cv", lambda league_id, n_folds: expected)

    assert backtest_engine.run_temporal_cv(9, 6) == expected

    execution = execution_store.list(execution_type="temporal_cv")[0]
    assert execution["status"] == "completed"
    assert execution["snapshot_hash"] == "snapshot-9"
    assert execution["parameters"]["requested_n_folds"] == 6
    assert execution["parameters"]["effective_parameters"]["window"] == 10
    assert execution["results"]["effective_parameters"]["n_folds"] == 4
    assert execution["results"]["metrics"]["mean_brier"] == 0.31
    assert execution["results"]["results"] == expected


def test_temporal_cv_failure_gets_terminal_execution(monkeypatch):
    monkeypatch.setattr(backtest_engine, "build_snapshot_manifest", _manifest)

    def fail(league_id, n_folds):
        raise RuntimeError("cv failed")

    monkeypatch.setattr(backtest_engine, "temporal_cv", fail)

    with pytest.raises(RuntimeError, match="cv failed"):
        backtest_engine.run_temporal_cv(10, 5)

    execution = execution_store.list(execution_type="temporal_cv")[0]
    assert execution["status"] == "failed"
    assert execution["results"]["error"] == "cv failed"


def test_cycle_execution_records_source_job_and_single_lifecycle(monkeypatch, tmp_path):
    monkeypatch.setattr(backtest_engine, "build_snapshot_manifest", _manifest)
    monkeypatch.setattr(backtest_engine, "_STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(backtest_engine, "_HISTORY_FILE", tmp_path / "history.jsonl")
    monkeypatch.setattr(backtest_engine, "get_model", lambda league_id: {
        "home_advantage": 1.2, "window": 8, "feature": "goals", "rho": 0.1,
    })
    loop = backtest_engine.BacktestLoop()
    monkeypatch.setattr(loop, "_backtest_league_meta", lambda league_id: {
        "league_id": league_id, "backtest": {"brier": 0.3}, "cv": {"mean_brier": 0.4},
    })

    result = loop._execute_cycle([42], source_job_id=123)

    assert result["leagues_processed"] == 1
    execution = execution_store.list(execution_type="backtest")[0]
    assert execution["status"] == "completed"
    assert execution["parameters"]["source_job_id"] == 123
    assert execution["parameters"]["effective_parameters"]["42"]["window"] == 8
    rows = db.run_query("SELECT event_type FROM execution_events WHERE execution_id=?",
                        (execution["execution_id"],))
    assert [row["event_type"] for row in rows] == ["started", "finished"]


def test_cycle_failure_gets_terminal_failed_execution(monkeypatch, tmp_path):
    monkeypatch.setattr(backtest_engine, "build_snapshot_manifest", _manifest)
    monkeypatch.setattr(backtest_engine, "_STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(backtest_engine, "_HISTORY_FILE", tmp_path / "history.jsonl")
    monkeypatch.setattr(backtest_engine, "get_model", lambda league_id: {
        "home_advantage": 1.2, "window": 8, "feature": "goals", "rho": 0.1,
    })
    loop = backtest_engine.BacktestLoop()
    monkeypatch.setattr(loop, "_append_history", lambda result: (_ for _ in ()).throw(
        RuntimeError("history write failed")))

    with pytest.raises(RuntimeError, match="history write failed"):
        loop._execute_cycle([43], source_job_id=124)

    execution = execution_store.list(execution_type="backtest")[0]
    assert execution["status"] == "failed"
    assert execution["parameters"]["source_job_id"] == 124
