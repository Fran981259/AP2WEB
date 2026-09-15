"""Focused integrity regressions for Sofascore synchronization."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from backend.app import db, jobs
from backend.app import sofascore_data as sofa
from backend.app.prediction import predict_fixture


def _league_and_teams(suffix: int):
    league_id = db.run_exec(
        "INSERT INTO leagues(sofascore_id,name,country) VALUES(?,?,?)",
        (800000 + suffix, f"Integrity {suffix}", "Test"),
    )
    home_id = db.run_exec("INSERT INTO teams(league_id,sofascore_id,name) VALUES(?,?,?)",
                          (league_id, 810000 + suffix, "Home"))
    away_id = db.run_exec("INSERT INTO teams(league_id,sofascore_id,name) VALUES(?,?,?)",
                          (league_id, 820000 + suffix, "Away"))
    return league_id, home_id, away_id


def _event(suffix: int, status: int = 100, timestamp: int = 1_700_000_000):
    return {
        "id": 830000 + suffix,
        "homeTeam": {"id": 810000 + suffix, "name": "Home"},
        "awayTeam": {"id": 820000 + suffix, "name": "Away"},
        "homeScore": {"current": 2},
        "awayScore": {"current": 1},
        "status": {"code": status},
        "startTimestamp": timestamp,
        "roundInfo": {"round": 4},
    }


def test_partial_sync_reports_failed_round_and_does_not_advance_freshness(monkeypatch):
    cfg = {"id": 840001, "name": "Partial", "country": "Test"}
    league_id = db.run_exec("INSERT INTO leagues(sofascore_id,name,last_sync) VALUES(?,?,?)",
                            (cfg["id"], cfg["name"], "2000-01-01"))
    event = _event(1)
    monkeypatch.setattr(sofa, "_latest_season", lambda _, heartbeat=None: (1, "2026"))
    monkeypatch.setattr(sofa, "_older_seasons", lambda *_: [])
    monkeypatch.setattr(sofa, "_season_rounds", lambda *_, heartbeat=None: ([1, 2], False))
    monkeypatch.setattr(sofa, "_fetch_round_events",
                        lambda *args, heartbeat=None: ([event], False) if args[-1] == 1 else ([], True))
    monkeypatch.setattr(sofa, "_fetch_all_events", lambda *_, heartbeat=None: ([], [3]))
    monkeypatch.setattr(sofa, "_upsert_match", lambda *_: True)

    result = sofa.sync_league(cfg)

    assert result["ok"] is False
    assert result["partial"] is True
    assert result["failed_rounds"] == [{"season_id": 1, "round": 2}]
    assert result["failed_pages"] == [{"season_id": 1, "page": 3}]
    assert db.run_query("SELECT last_sync FROM leagues WHERE id=?", (league_id,))[0]["last_sync"] == "2000-01-01"


def test_sync_job_fails_and_retains_partial_result(monkeypatch):
    user_id = db.run_exec(
        "INSERT INTO users(username,password_hash,role) VALUES(?,?,?)",
        ("sync-integrity-user", "not-used", "admin"),
    )
    league_id, _, _ = _league_and_teams(2)
    job = jobs.create_job("sync_league", requested_by=user_id, league_id=league_id,
                          parameters={"integrity": True})
    outcome = {"ok": False, "partial": True, "failed_pages": [{"page": 3}]}
    monkeypatch.setattr("backend.app.sofascore_data.sync_league_local", lambda _, heartbeat=None: outcome)

    jobs._run_one(job)

    saved = jobs.get_job(job["id"])
    assert saved["status"] == "failed"
    assert json.loads(saved["result"]) == outcome


def test_played_match_retries_missing_stats_on_later_sync(monkeypatch):
    league_id, home_id, away_id = _league_and_teams(3)
    event = _event(3)
    db.run_exec(
        "INSERT INTO matches(league_id,sofascore_id,home_team_id,away_team_id,status,score_home,score_away) "
        "VALUES(?,?,?,?,?,?,?)",
        (league_id, event["id"], home_id, away_id, "played", 2, 1),
    )
    calls = []
    monkeypatch.setattr(sofa, "_fetch", lambda *args: calls.append(args[0]) or {})
    monkeypatch.setattr(sofa, "_extract_stats", lambda _: {"xg": {"home": 1.4, "away": 0.6}})

    sofa._upsert_match(league_id, event)

    row = db.run_query("SELECT xg_home,xg_away FROM matches WHERE league_id=? AND sofascore_id=?",
                       (league_id, event["id"]))[0]
    assert (row["xg_home"], row["xg_away"]) == (1.4, 0.6)
    assert calls


def test_scheduled_or_unknown_source_cannot_regress_played_match():
    league_id, home_id, away_id = _league_and_teams(4)
    event = _event(4)
    match_id = db.run_exec(
        "INSERT INTO matches(league_id,sofascore_id,home_team_id,away_team_id,status,score_home,score_away) "
        "VALUES(?,?,?,?,?,?,?)",
        (league_id, event["id"], home_id, away_id, "played", 2, 1),
    )

    sofa._upsert_match(league_id, _event(4, status=0))
    sofa._upsert_match(league_id, _event(4, status=999))

    row = db.run_query("SELECT status,score_home,score_away FROM matches WHERE id=?", (match_id,))[0]
    assert (row["status"], row["score_home"], row["score_away"]) == ("played", 2, 1)


def test_kickoff_correction_updates_match_date_and_keeps_round(monkeypatch):
    league_id, home_id, away_id = _league_and_teams(5)
    event = _event(5, timestamp=1_700_000_000)
    match_id = db.run_exec(
        "INSERT INTO matches(league_id,sofascore_id,home_team_id,away_team_id,kickoff_datetime,match_date,round,status) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (league_id, event["id"], home_id, away_id, "2020-01-01T00:00:00+00:00", "2020-01-01", 9,
         "scheduled"),
    )
    event.pop("roundInfo")
    monkeypatch.setattr(sofa, "_fetch", lambda *_: {})

    sofa._upsert_match(league_id, event)

    row = db.run_query("SELECT kickoff_datetime,match_date,round FROM matches WHERE id=?", (match_id,))[0]
    assert row["kickoff_datetime"] == "2023-11-14T22:13:20+00:00"
    assert row["match_date"] == "2023-11-14"
    assert row["round"] == 9


def test_historical_ingestion_uses_ingestion_time_for_prediction_freshness(monkeypatch):
    league_id, home_id, away_id = _league_and_teams(6)
    historical = _event(6, timestamp=946_684_800)  # 2000-01-01 UTC
    monkeypatch.setattr(sofa, "_fetch", lambda *_: {})

    sofa._upsert_match(league_id, historical)

    ingested_at = db.run_query(
        "SELECT source_ingested_at, kickoff_datetime FROM matches WHERE league_id=?", (league_id,))[0]
    result = predict_fixture(league_id, home_id, away_id)

    assert ingested_at["kickoff_datetime"].startswith("2000-01-01")
    assert ingested_at["source_ingested_at"] is not None
    assert datetime.fromisoformat(ingested_at["source_ingested_at"]).date() == datetime.now(timezone.utc).date()
    assert result["provenance"]["source_data_freshness"] == ingested_at["source_ingested_at"]
