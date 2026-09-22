"""Numerical invariants and regression counterexamples from the deep audit."""
from collections import deque

import pytest

from backend.app import db, learning, prediction
from backend.app.feature_engine import compute_match_stats, compute_team_stats, window_stats
from backend.app.model import build_gamma_poisson_matrix, build_matrix, dixon_coles_tau


@pytest.fixture
def match_history(tmp_path, monkeypatch):
    monkeypatch.setattr(db.env, "DB_PATH", tmp_path / "scientific.db")
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


def test_gamma_poisson_matrix_is_probability_distribution():
    values = [p for row in build_gamma_poisson_matrix(3.7, 2.2, 2.1, 1.8) for p in row]
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


def test_completed_match_requires_both_scores():
    with pytest.raises(ValueError, match="both scores"):
        compute_match_stats({"score_home": 4}, "goals")


def test_window_stats_selects_newest_matches_regardless_of_input_order():
    matches = [
        {"id": 1, "kickoff_datetime": "2020-01-01", "home_team_id": 1, "away_team_id": 2, "score_home": 1, "score_away": 0},
        {"id": 3, "kickoff_datetime": "2020-03-01", "home_team_id": 1, "away_team_id": 2, "score_home": 5, "score_away": 0},
        {"id": 2, "kickoff_datetime": "2020-02-01", "home_team_id": 1, "away_team_id": 2, "score_home": 3, "score_away": 0},
    ]
    assert window_stats(matches, 1, 2, "goals")["gf_avg"] == 4


@pytest.mark.parametrize("feature,expected", [("goals", (1, 3)), ("xg", (0.6, 2.4)), ("blend", (0.8, 2.7))])
def test_prediction_features_follow_team_perspective(match_history, feature, expected):
    lid, _, away, _ = match_history
    stats = prediction._avg_stats(lid, away, 10, feature, "2020-02-01")
    assert (stats["gf_avg"], stats["ga_avg"]) == pytest.approx(expected)
    detail = prediction._avg_stats_detail(lid, away, 10, feature, "2020-02-01")
    assert (detail["games_used"][0]["gf"], detail["games_used"][0]["ga"]) == pytest.approx(expected)


def test_bayesian_override_with_context_is_deterministic(match_history, monkeypatch):
    lid, home, away, _ = match_history
    monkeypatch.setattr(prediction.builder, "_model_for", lambda _: {
        "feature": "goals", "window": 10, "home_advantage": 1.15,
        "rho": 0, "method": "hybrid", "ctx_form": 1})
    one = prediction.predict_fixture(lid, home, away, use_bayesian=False)
    two = prediction.predict_fixture(lid, home, away, use_bayesian=False)
    assert one["probs"] == two["probs"]


def test_bayesian_uses_the_model_feature(match_history, monkeypatch):
    lid, home, away, _ = match_history
    monkeypatch.setattr(prediction.builder, "_model_for", lambda _: {
        "feature": "xg", "window": 10, "home_advantage": 1.15,
        "rho": 0, "method": "bayesian", "ctx_form": 0})
    result = prediction.predict_fixture(lid, home, away)
    assert result["bayesian"]["inputs"]["home"]["gf_avg"] == pytest.approx((1.3 + 2.4) / 6)


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


def test_match_prediction_uses_kickoff_as_default_cutoff(match_history, monkeypatch):
    lid, home, away, match_id = match_history
    captured = {}

    def fake_build(*args, **kwargs):
        captured["cutoff"] = args[-2]
        return {"ok": True}

    monkeypatch.setattr(prediction.service, "_build", fake_build)
    assert prediction.predict_match(match_id) == {"ok": True}
    assert captured["cutoff"] == "2020-01-01T12:00:00+00:00"
    with pytest.raises(ValueError, match="cannot be after"):
        prediction.predict_match(match_id, "2020-01-02T12:00:00+00:00")


def test_backtest_does_not_leak_between_same_kickoff_fixtures(match_history, monkeypatch):
    lid, home, away, _ = match_history
    for score_home, score_away in [(9, 0), (0, 2)]:
        db.run_exec(
            "INSERT INTO matches(league_id,home_team_id,away_team_id,kickoff_datetime,status,score_home,score_away) VALUES(?,?,?,?,?,?,?)",
            (lid, home, away, "2020-02-01T12:00:00+00:00", "played", score_home, score_away))
    observed = []

    def fake_probs(home_stats, away_stats, *_args):
        observed.append((home_stats["gf_avg"], away_stats["gf_avg"]))
        return {"1": 0.4, "X": 0.2, "2": 0.4}

    monkeypatch.setattr(learning.walkforward, "MIN_SAMPLES", 1)
    monkeypatch.setattr(learning.walkforward, "_predict_probs", fake_probs)
    result = learning.backtest_league(lid, feature="goals")
    assert result["total"] == 2
    assert observed == [(3.0, 1.0), (3.0, 1.0)]
