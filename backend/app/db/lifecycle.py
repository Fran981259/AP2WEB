"""Database lifecycle: init, seed, full reset."""
from __future__ import annotations

import sqlite3

from . import env
from .env import _pg_connect
from .migrations import (
    _ensure_execution_events,
    _ensure_job_cols,
    _ensure_league_model_cols,
    _ensure_match_source_cols,
    _ensure_prediction_updated_at,
    _ensure_provenance_cols,
    _ensure_user_cols,
    _record_migration,
)
from .schema import SCHEMA
from .session import get_conn
from .translate import _PG_SCHEMA


def init_db() -> None:
    if env.MODE == "sqlite":
        conn = get_conn()
        try:
            conn.executescript(SCHEMA)
            try:
                conn.execute("INSERT OR IGNORE INTO schema_migrations(version) VALUES(?)", ("20260909_baseline",))
                # Commit and release the write lock BEFORE opening a second
                # connection (migrations below), to avoid an sqlite file-lock
                # deadlock between connections in the same process.
                conn.commit()
            except Exception:
                pass
            # ensure provenance cols for existing DBs before 2nd stabilization
            try:
                cols=[r[1] for r in conn.execute("PRAGMA table_info(predictions)").fetchall()]
                for col, typ in [("model_method","TEXT"),("feature_version","TEXT"),("data_snapshot_timestamp","TEXT"),
                                 ("as_of_timestamp","TEXT"),("training_window","INTEGER"),("training_sample_size","INTEGER"),
                                 ("league_model_version","TEXT"),("source_data_freshness","TEXT"),("confidence_level","TEXT"),("fallback_reason","TEXT")]:
                    if col not in cols:
                        conn.execute(f"ALTER TABLE predictions ADD COLUMN {col} {typ}")
                # jobs already in SCHEMA via IF NOT EXISTS
            except Exception:
                pass
            _seed_leagues(conn)
            conn.commit()
        finally:
            conn.close()
        # Run ALTER TABLE work only after the schema/seed connection has been
        # fully closed. SQLite serializes writers and otherwise can wait on a
        # lock held by this same process during repeated app startup/tests.
        _ensure_user_cols()
        _ensure_job_cols()
        _ensure_match_source_cols()
        _ensure_execution_events()
        _ensure_prediction_updated_at()
        _ensure_league_model_cols()
        _record_migration("20260914_source_ingestion")
        _record_migration("20260914_execution_events")
        _record_migration("20260922_projection_hardening")
        return
    with _pg_connect() as conn:
        # API replicas and the standalone worker may start together during a rollout.
        # A session advisory lock serializes their schema work without a separate migrator.
        conn.execute("SELECT pg_advisory_lock(92220260914)")
        try:
            for stmt in _PG_SCHEMA.split(";"):
                if stmt.strip():
                    conn.execute(stmt)
            try:
                conn.execute("INSERT INTO schema_migrations(version) VALUES(%s) ON CONFLICT DO NOTHING", ("20260909_baseline",))
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            _ensure_provenance_cols()
            _ensure_user_cols()
            _ensure_job_cols()
            _ensure_match_source_cols()
            _ensure_execution_events()
            _ensure_prediction_updated_at()
            _ensure_league_model_cols()
            _record_migration("20260914_source_ingestion")
            _record_migration("20260914_execution_events")
            _record_migration("20260922_projection_hardening")
        finally:
            conn.execute("SELECT pg_advisory_unlock(92220260914)")
def _seed_leagues(conn: sqlite3.Connection) -> None:
    """Insere ligas do leagues_config.py se a tabela estiver vazia."""
    count = conn.execute("SELECT COUNT(*) FROM leagues").fetchone()[0]
    if count > 0:
        return
    try:
        from ..leagues_config import LEAGUES
    except ImportError:
        return
    for lg in LEAGUES:
        conn.execute(
            "INSERT OR IGNORE INTO leagues(sofascore_id, name, country) VALUES(?,?,?)",
            (lg["id"], lg["name"], lg["country"]))
    conn.commit()
def reset_db() -> None:
    """Remove todas as tabelas e recria (banco novo do zero)."""
    if env.MODE == "sqlite":
        conn = get_conn()
        try:
            conn.execute("PRAGMA foreign_keys=OFF")
            tables = [r["name"] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
            for t in tables:
                conn.execute(f'DROP TABLE IF EXISTS "{t}"')
            conn.commit()
            conn.executescript(SCHEMA)
            conn.commit()
        finally:
            conn.close()
        return
    with _pg_connect() as conn:
        rows = conn.execute(
            "SELECT tablename AS name FROM pg_tables WHERE schemaname='public'")
        for r in rows.fetchall():
            conn.execute(f'DROP TABLE IF EXISTS "{r["name"]}" CASCADE')
        for stmt in _PG_SCHEMA.split(";"):
            if stmt.strip():
                conn.execute(stmt)
