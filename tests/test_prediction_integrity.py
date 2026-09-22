"""Phase 4 prediction-save integrity regressions."""
from datetime import datetime, timedelta, timezone

import pytest

from backend.app import db
from backend.app.history import resolve_predictions, save_prediction
from backend.app.sofascore import _upsert_match


def _future_match():
    league_id = db.run_query("SELECT id FROM leagues ORDER BY id LIMIT 1")[0]["id"]
    home = db.run_exec("INSERT INTO teams(league_id,name) VALUES(?,?)", (league_id, "Canonical Home"))
    away = db.run_exec("INSERT INTO teams(league_id,name) VALUES(?,?)", (league_id, "Canonical Away"))
    kickoff = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    match_id = db.run_exec(
        "INSERT INTO matches(league_id,home_team_id,away_team_id,kickoff_datetime,status) VALUES(?,?,?,?,?)",
        (league_id, home, away, kickoff, "scheduled"))
    return league_id, home, away, match_id, kickoff


def _data(league_id, home, away, match_id, **overrides):
    return {
        "league_id": league_id,
        "match_id": match_id,
        "home_team_id": home,
        "away_team_id": away,
        "home_name": "client supplied home",
        "away_name": "client supplied away",
        "match_date": "1999-01-01",
        "pick_type": "1X2",
        "pick_value": "1",
        "pick_label": "home",
        "prob": 0.625,
        "odd": 1.6,
        "payload": {},
    } | overrides


def test_save_uses_decimal_ui_probability_and_canonical_match_fields():
    league_id, home, away, match_id, kickoff = _future_match()
    saved = save_prediction(1, _data(league_id, home, away, match_id))
    assert saved["prob"] == pytest.approx(0.625)
    assert saved["league_id"] == league_id
    assert saved["home_team_id"] == home
    assert saved["away_team_id"] == away
    assert saved["home_name"] == "Canonical Home"
    assert saved["away_name"] == "Canonical Away"
    assert saved["match_date"] == kickoff[:10]
    assert saved["model_version"] is not None


def test_missing_canonical_context_does_not_persist_client_provenance(monkeypatch):
    league_id, home, away, match_id, _ = _future_match()

    def unavailable(_match_id):
        raise ValueError("unavailable")

    from backend.app import prediction
    monkeypatch.setattr(prediction, "predict_match", unavailable)
    saved = save_prediction(1, _data(league_id, home, away, match_id,
                                     model_version="client-fake", model_method="client-fake"))
    assert saved["model_version"] is None
    assert saved["model_method"] is None


@pytest.mark.parametrize("pick_type,pick_value", [
    ("PLACAR", "1-0"), ("1X2", "home"), ("GOLS", "over_2.5junk"), ("BTTS", "yes"),
])
def test_invalid_picks_are_rejected(pick_type, pick_value):
    league_id, home, away, match_id, _ = _future_match()
    with pytest.raises(ValueError, match="jogada não suportada"):
        save_prediction(1, _data(league_id, home, away, match_id,
                                 pick_type=pick_type, pick_value=pick_value))


def test_mismatched_or_played_matches_are_rejected():
    league_id, home, away, match_id, _ = _future_match()
    with pytest.raises(ValueError, match="não corresponde"):
        save_prediction(1, _data(league_id, home + 999, away, match_id))
    db.run_exec("UPDATE matches SET status='played', score_home=1, score_away=0 WHERE id=?", (match_id,))
    with pytest.raises(ValueError, match="agendadas"):
        save_prediction(1, _data(league_id, home, away, match_id))


def test_scheduled_rematch_stays_pending_when_another_rematch_is_played():
    league_id, home, away, match_id, _ = _future_match()
    saved = save_prediction(1, _data(league_id, home, away, match_id))
    db.run_exec(
        "INSERT INTO matches(league_id,home_team_id,away_team_id,kickoff_datetime,status,score_home,score_away) VALUES(?,?,?,?,?,?,?)",
        (league_id, home, away, "2020-01-01T12:00:00+00:00", "played", 4, 0))
    assert resolve_predictions(1) == 0
    row = db.run_query("SELECT status FROM predictions WHERE id=?", (saved["id"],))[0]
    assert row["status"] == "pending"


def test_completed_upsert_resolves_its_pending_predictions_once(monkeypatch):
    league_id = db.run_query("SELECT id FROM leagues ORDER BY id LIMIT 1")[0]["id"]
    home = db.run_exec("INSERT INTO teams(league_id,sofascore_id,name) VALUES(?,?,?)",
                       (league_id, 90001, "Sync Home"))
    away = db.run_exec("INSERT INTO teams(league_id,sofascore_id,name) VALUES(?,?,?)",
                       (league_id, 90002, "Sync Away"))
    match_id = db.run_exec(
        "INSERT INTO matches(league_id,sofascore_id,home_team_id,away_team_id,status) VALUES(?,?,?,?,?)",
        (league_id, 90003, home, away, "scheduled"))
    prediction_id = db.run_exec(
        "INSERT INTO predictions(user_id,match_id,pick_type,pick_value,prob) VALUES(?,?,?,?,?)",
        (1, match_id, "1X2", "1", 0.625))
    event = {
        "id": 90003,
        "homeTeam": {"id": 90001, "name": "Sync Home"},
        "awayTeam": {"id": 90002, "name": "Sync Away"},
        "homeScore": {"current": 2},
        "awayScore": {"current": 0},
        "status": {"code": 100},
    }
    monkeypatch.setattr("backend.app.sofascore.upserts._fetch", lambda *_: {})

    _upsert_match(league_id, event | {"status": {"code": 0}})
    pending = db.run_query("SELECT status FROM predictions WHERE id=?", (prediction_id,))[0]
    assert pending["status"] == "pending"

    _upsert_match(league_id, event)
    resolved = db.run_query(
        "SELECT status,resolved_at FROM predictions WHERE id=?", (prediction_id,))[0]
    assert resolved["status"] == "correct"
    assert resolved["resolved_at"] is not None

    _upsert_match(league_id, event)
    repeated = db.run_query(
        "SELECT status,resolved_at FROM predictions WHERE id=?", (prediction_id,))[0]
    assert dict(repeated) == dict(resolved)
