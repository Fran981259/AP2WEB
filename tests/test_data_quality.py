"""Regression tests for the data-quality gates used before calibration."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.app import data_quality, db


def _league(name: str) -> int:
    return db.run_exec(
        "INSERT INTO leagues(sofascore_id,name,country,last_sync) VALUES(?,?,?,?)",
        (990000 + len(name), name, "Test", datetime.now(timezone.utc).isoformat()),
    )


def test_quality_requires_complete_results_and_xg_coverage():
    league_id = _league("Quality incomplete")
    for index in range(60):
        db.run_exec(
            "INSERT INTO matches(league_id,sofascore_id,status,score_home,score_away,xg_home,xg_away) "
            "VALUES(?,?,?,?,?,?,?)",
            (league_id, 991000 + index, "played", 1, 0,
             1.1 if index < 47 else None, 0.7 if index < 47 else None),
        )
    item = next(row for row in data_quality.league_quality() if row["league_id"] == league_id)
    assert item["status"] == "incomplete"
    assert item["xg_coverage"] == pytest.approx(47 / 60, abs=0.0001)


def test_quality_marks_fresh_complete_history_as_ready():
    league_id = _league("Quality ready")
    for index in range(60):
        db.run_exec(
            "INSERT INTO matches(league_id,sofascore_id,status,score_home,score_away,xg_home,xg_away) "
            "VALUES(?,?,?,?,?,?,?)",
            (league_id, 992000 + index, "played", 2, 1, 1.5, 0.8),
        )
    item = next(row for row in data_quality.league_quality() if row["league_id"] == league_id)
    assert item["status"] == "ready"
    assert item["results_coverage"] == 1.0
    assert item["xg_coverage"] == 1.0
