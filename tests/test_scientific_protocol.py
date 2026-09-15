from backend.app import db, learning
import pytest

from backend.app.scientific_protocol import (
    build_snapshot_manifest,
    run_scientific_protocol,
    scientific_metrics,
    temporal_split,
)


def _insert_match(league_id, home, away, date, score_home=1, score_away=0):
    return db.run_exec(
        "INSERT INTO matches(league_id,home_team_id,away_team_id,kickoff_datetime,status,score_home,score_away) "
        "VALUES(?,?,?,?,?,?,?)",
        (league_id, home, away, date, "played", score_home, score_away),
    )


def test_snapshot_hash_is_deterministic_and_league_scoped(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "protocol.db")
    db.init_db()
    league_id = db.run_query("SELECT id FROM leagues ORDER BY id LIMIT 1")[0]["id"]
    home = db.run_exec("INSERT INTO teams(league_id,name) VALUES(?,?)", (league_id, "Home"))
    away = db.run_exec("INSERT INTO teams(league_id,name) VALUES(?,?)", (league_id, "Away"))
    _insert_match(league_id, home, away, "2024-01-01T12:00:00+00:00")

    first = build_snapshot_manifest(league_id)
    second = build_snapshot_manifest(league_id)

    assert first["hash"] == second["hash"]
    assert first["completed_match_count"] == 1
    assert first["usable_match_count"] == 1


def test_temporal_split_reserves_newest_rows_and_validates_fraction():
    rows = [{"id": n, "kickoff_datetime": f"2024-01-0{n}T00:00:00+00:00"} for n in range(1, 6)]
    split = temporal_split(rows, 0.4)

    assert [row["id"] for row in split["development"]] == [1, 2, 3]
    assert [row["id"] for row in split["holdout"]] == [4, 5]

    with pytest.raises(ValueError):
        temporal_split(rows, 0)


def test_protocol_blocks_empty_data_and_runs_supplied_backtest(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "protocol.db")
    db.init_db()
    assert run_scientific_protocol()["status"] == "blocked"

    league_id = db.run_query("SELECT id FROM leagues ORDER BY id LIMIT 1")[0]["id"]
    home = db.run_exec("INSERT INTO teams(league_id,name) VALUES(?,?)", (league_id, "Home"))
    away = db.run_exec("INSERT INTO teams(league_id,name) VALUES(?,?)", (league_id, "Away"))
    _insert_match(league_id, home, away, "2024-01-01T12:00:00+00:00")
    _insert_match(league_id, away, home, "2024-01-02T12:00:00+00:00")
    result = run_scientific_protocol(league_id, backtest=lambda rows: {"rows": len(rows)})

    assert result["status"] == "prepared"
    assert result["walk_forward"] == {"rows": 1}
    assert result["promotion_enabled"] is False


def test_protocol_uses_development_only_for_selection_and_holdout_for_final_evaluation(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "protocol.db")
    db.init_db()
    league_id = db.run_query("SELECT id FROM leagues ORDER BY id LIMIT 1")[0]["id"]
    home = db.run_exec("INSERT INTO teams(league_id,name) VALUES(?,?)", (league_id, "Home"))
    away = db.run_exec("INSERT INTO teams(league_id,name) VALUES(?,?)", (league_id, "Away"))
    for day in range(1, 6):
        _insert_match(league_id, home, away, f"2024-01-0{day}T12:00:00+00:00")

    calls = []

    def canonical(rows, **kwargs):
        calls.append(([row["id"] for row in rows], kwargs.get("evaluation_start", 0)))
        start = kwargs.get("evaluation_start", 0)
        predictions = [
            {"actual": "1", "probabilities": {"1": 0.6, "X": 0.2, "2": 0.2}}
            for _ in rows[start:]
        ]
        return {"total": len(predictions), "predictions": predictions}

    monkeypatch.setattr(learning, "backtest_completed_matches", canonical)
    result = run_scientific_protocol(league_id, fixed_parameters={"window": 5})

    development_ids = [row["id"] for row in result["split"]["development"]]
    holdout_ids = [row["id"] for row in result["split"]["holdout"]]
    assert result["status"] == "completed"
    assert result["parameter_selection"] == "not_performed_fixed_parameters"
    assert calls[0] == (development_ids, 0)
    assert calls[1] == (development_ids + holdout_ids, len(development_ids))
    assert result["metrics"]["development"]["status"] == "completed"
    assert result["metrics"]["holdout"]["samples"] == len(holdout_ids)


def test_scientific_metrics_are_deterministic_and_follow_multiclass_invariants():
    records = {
        "predictions": [
            {"actual": "1", "probabilities": {"1": 1.0, "X": 0.0, "2": 0.0}},
            {"actual": "X", "probabilities": {"1": 0.0, "X": 1.0, "2": 0.0}},
            {"actual": "2", "probabilities": {"1": 0.0, "X": 0.0, "2": 1.0}},
        ]
    }

    first = scientific_metrics(records, bootstrap_resamples=50, bootstrap_seed=123)
    second = scientific_metrics(records, bootstrap_resamples=50, bootstrap_seed=123)

    assert first == second
    assert first["brier"] == 0
    assert first["logloss"] == 0
    assert first["rps"] == 0
    assert 0 <= first["rps"] <= 1
    for summary in first["calibration"].values():
        assert summary["calibration_gap"] == 0
    assert sum(summary["mean_predicted_probability"]
               for summary in first["calibration"].values()) == pytest.approx(1)
    assert sum(summary["observed_frequency"]
               for summary in first["calibration"].values()) == pytest.approx(1)
    assert first["bootstrap"]["brier"] == {"lower": 0.0, "upper": 0.0}


def test_scientific_metrics_block_missing_prediction_records():
    assert scientific_metrics({"total": 1}, bootstrap_resamples=1) == {
        "status": "insufficient_data",
        "reason": "no_scored_prediction_records",
        "samples": 0,
    }


def test_temporal_split_keeps_same_kickoff_rows_together():
    rows = [
        {"id": 1, "kickoff_datetime": "2024-01-01T00:00:00+00:00"},
        {"id": 2, "kickoff_datetime": "2024-01-02T00:00:00+00:00"},
        {"id": 3, "kickoff_datetime": "2024-01-03T00:00:00+00:00"},
        {"id": 4, "kickoff_datetime": "2024-01-03T00:00:00+00:00"},
    ]

    split = temporal_split(rows, 0.25)

    assert [row["id"] for row in split["development"]] == [1, 2]
    assert [row["id"] for row in split["holdout"]] == [3, 4]


def test_protocol_baselines_exclude_holdout_outcomes_and_report_comparison(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "protocol.db")
    db.init_db()
    league_id = db.run_query("SELECT id FROM leagues ORDER BY id LIMIT 1")[0]["id"]
    home = db.run_exec("INSERT INTO teams(league_id,name) VALUES(?,?)", (league_id, "Home"))
    away = db.run_exec("INSERT INTO teams(league_id,name) VALUES(?,?)", (league_id, "Away"))
    for day in range(1, 5):
        _insert_match(league_id, home, away, f"2024-01-0{day}T12:00:00+00:00", 1, 0)
    _insert_match(league_id, home, away, "2024-01-05T12:00:00+00:00", 0, 1)
    _insert_match(league_id, home, away, "2024-01-06T12:00:00+00:00", 0, 1)

    result = run_scientific_protocol(
        league_id, holdout_fraction=0.25,
        fixed_parameters={"home_adv": 1.15, "window": 5, "feature": "goals", "rho": 0.0},
        bootstrap_resamples=5,
    )

    empirical_holdout = result["baselines"]["league_empirical_1x2"]["holdout"]["predictions"]
    assert len(empirical_holdout) == result["metrics"]["holdout"]["samples"] == 2
    assert [prediction["probabilities"] for prediction in empirical_holdout] == [
        {"1": 1.0, "X": 0.0, "2": 0.0},
        {"1": 1.0, "X": 0.0, "2": 0.0},
    ]
    assert result["baselines"]["neutral_independent_poisson"]["parameters"] == {
        "lam_home": 1.2, "lam_away": 1.2, "rho": 0.0,
    }
    assert result["comparison"]["decision"] == "not_performed"
    assert result["comparison"]["holdout"]["candidate"] == result["metrics"]["holdout"]
    assert set(result["comparison"]["holdout"]["baselines"]) == {
        "league_empirical_1x2", "neutral_independent_poisson",
    }
