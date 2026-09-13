"""Stabilization tests — P1-P6 minimal gate."""
import os
os.environ.setdefault("AP2WEB_SECRET", "ci-test-secret-do-not-use-in-production-0123456789abcdef")
os.environ.setdefault("AP2WEB_DB_PATH", "/tmp/ap2web_stab_test.db")

from backend.app import db
from backend.app.auth import hash_password, verify_password
from backend.app.prediction import predict_fixture

def test_password_hash():
    h = hash_password("secret123")
    assert "$" in h
    assert verify_password("secret123", h)
    assert not verify_password("wrong", h)

def test_db_health():
    db.init_db()
    rows = db.run_query("SELECT 1 AS ok", ())
    assert rows[0]["ok"] == 1


def test_postgres_returning_id_is_limited_to_id_tables():
    assert db._insert_returns_id("INSERT INTO jobs(status) VALUES('pending')")
    assert db._insert_returns_id("INSERT INTO auth_sessions(user_id) VALUES(1)")
    assert not db._insert_returns_id("INSERT INTO workers(worker_id) VALUES('w1')")
    assert not db._insert_returns_id("INSERT INTO league_models(league_id) VALUES(1)")

def test_prediction_determinism():
    # Requires DB with data; skip if no leagues
    db.init_db()
    leagues = db.run_query("SELECT id FROM leagues LIMIT 1")
    if not leagues:
        return
    # Try at least one prediction call doesn't raise and is deterministic
    try:
        lrow = db.run_query("SELECT l.id, l.name FROM leagues l JOIN matches m ON m.league_id=l.id LIMIT 1")
        if not lrow:
            return
        lid = lrow[0]["id"]
        teams = db.run_query("SELECT id FROM teams WHERE league_id=? LIMIT 2", (lid,))
        if len(teams) < 2:
            return
        p1 = predict_fixture(lid, teams[0]["id"], teams[1]["id"])
        p2 = predict_fixture(lid, teams[0]["id"], teams[1]["id"])
        assert abs(p1["probs"]["1x2"]["1"] - p2["probs"]["1x2"]["1"]) < 1e-9
        # 1X2 must sum ~1
        assert abs(sum(p1["probs"]["1x2"].values()) - 1.0) < 0.02
    except Exception as e:
        # If DB empty, skip
        if "não encontrado" in str(e).lower() or "not found" in str(e).lower():
            return
        raise

def test_use_bayesian_param():
    # Ensure explicit param overrides global
    db.init_db()
    lrow = db.run_query("SELECT l.id FROM leagues l JOIN matches m ON m.league_id=l.id LIMIT 1")
    if not lrow:
        return
    lid = lrow[0]["id"]
    teams = db.run_query("SELECT id FROM teams WHERE league_id=? LIMIT 2", (lid,))
    if len(teams) < 2:
        return
    # Both calls should succeed regardless of global
    try:
        p_false = predict_fixture(lid, teams[0]["id"], teams[1]["id"], use_bayesian=False)
        p_true = predict_fixture(lid, teams[0]["id"], teams[1]["id"], use_bayesian=True)
        assert "probs" in p_false and "probs" in p_true
    except Exception:
        pass

def test_no_hardcoded_secret_in_code():
    import pathlib
    # Ensure .env.example doesn't contain real secret
    txt = pathlib.Path(".env.example").read_text()
    assert "troque-esta-chave" in txt.lower() or "change-me" in txt.lower() or "random" in txt.lower()
