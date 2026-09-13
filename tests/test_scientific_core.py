"""Numerical invariants and regression counterexamples from the deep audit."""
from collections import deque

import pytest

from backend.app import db, prediction
from backend.app.feature_engine import compute_match_stats, compute_team_stats
from backend.app.model import build_matrix, dixon_coles_tau


@pytest.fixture
def match_history(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "scientific.db")
    db.init_db()
    lid = db.run_query("SELECT id FROM leagues ORDER BY id LIMIT 1")[0]["id"]
    home = db.run_exec("INSERT INTO teams(league_id,name) VALUES(?,?)", (lid, "Home"))
    away = db.run_exec("INSERT INTO teams(league_id,name) VALUES(?,?)", (lid, "Away"))
    mid = db.run_exec(
        "INSERT INTO matches(league_id,home_team_id,away_team_id,kickoff_datetime,status,score_home,score_away,xg_home,xg_away) VALUES(?,?,?,?,?,?,?,?,?)",
        (lid, home, away, "2020-01-01T12:00:00+00:00", "played", 3, 1, 2.4, 0.6))
    return lid, home, away, mid


@pytest.mark.parametrize("i,j,expected", [(0, 0, 1.156), (1, 0, 0.87), (0, 1, 0.88), (1, 1, 1.1), (2, 2, 1)])
def test_canonical_dixon_coles(i, j, expected):
    assert dixon_coles_tau(i, j, 1.2, 1.3, -0.1) == pytest.approx(expected)


def test_matrix_is_probability_distribution():
    for lh, la in [(0, 0), (0.2, 0.3), (1.2, 1.3), (3, 4), (8, 6)]:
        for rho in [-0.5, -0.2, 0, 0.5]:
            values = [p for row in build_matrix(lh, la, rho) for p in row]
            assert min(values) >= 0
            assert sum(values) == pytest.approx(1)


def test_blend_is_selected_once():
    selected = compute_match_stats({"score_home": 4, "score_away": 2, "xg_home": 2, "xg_away": 1}, "blend")
    averages = compute_team_stats(deque([selected]), 10, "blend")
    assert averages["gf_avg"] == 3
    assert averages["ga_avg"] == 1.5
    assert averages["xga_avg"] == 1


def test_missing_xg_is_not_zero():
    assert compute_match_stats({"score_home": 4, "score_away": 2}, "blend")["gf"] == 4


@pytest.mark.parametrize("feature,expected", [("goals", (1, 3)), ("xg", (0.6, 2.4)), ("blend", (0.8, 2.7))])
def test_prediction_features_follow_team_perspective(match_history, feature, expected):
    lid, _, away, _ = match_history
    stats = prediction._avg_stats(lid, away, 10, feature, "2020-02-01")
    assert (stats["gf_avg"], stats["ga_avg"]) == pytest.approx(expected)
    detail = prediction._avg_stats_detail(lid, away, 10, feature, "2020-02-01")
    assert (detail["games_used"][0]["gf"], detail["games_used"][0]["ga"]) == pytest.approx(expected)


def test_bayesian_override_with_context_is_deterministic(match_history, monkeypatch):
    lid, home, away, _ = match_history
    monkeypatch.setattr(prediction, "_model_for", lambda _: {
        "feature": "goals", "window": 10, "home_advantage": 1.15,
        "rho": 0, "method": "hybrid", "ctx_form": 1})
    one = prediction.predict_fixture(lid, home, away, use_bayesian=False)
    two = prediction.predict_fixture(lid, home, away, use_bayesian=False)
    assert one["probs"] == two["probs"]


def test_sqlite_write_count_contract(match_history):
    _, _, _, mid = match_history
    assert db.run_exec("UPDATE matches SET round=1 WHERE id=?", (mid,)) == 1
    assert db.run_exec("DELETE FROM matches WHERE id=?", (-1,)) == 0


def test_scheduled_match_is_only_prediction_candidate(match_history):
    lid, home, away, _ = match_history
    scheduled = db.run_exec(
        "INSERT INTO matches(league_id,home_team_id,away_team_id,kickoff_datetime,status) VALUES(?,?,?,?,?)",
        (lid, home, away, "2030-01-01T12:00:00+00:00", "scheduled"))
    assert [p["match"]["id"] for p in prediction.predict_league_upcoming(lid)] == [scheduled]
