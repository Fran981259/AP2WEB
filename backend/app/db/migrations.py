"""Idempotent schema migrations for pre-existing databases."""
from __future__ import annotations

from . import env
from .session import run_exec, run_query


def _ensure_provenance_cols():
    for col, typ in [("model_method","TEXT"),("feature_version","TEXT"),("data_snapshot_timestamp","TEXT"),
                     ("as_of_timestamp","TEXT"),("training_window","INTEGER"),("training_sample_size","INTEGER"),
                     ("league_model_version","TEXT"),("source_data_freshness","TEXT"),("confidence_level","TEXT"),("fallback_reason","TEXT")]:
        try:
            if env.MODE=="sqlite":
                cols=[r[1] for r in run_query("PRAGMA table_info(predictions)")]
                if col not in cols:
                    run_exec(f"ALTER TABLE predictions ADD COLUMN {col} {typ}")
            else:
                run_exec(f"ALTER TABLE predictions ADD COLUMN IF NOT EXISTS {col} {typ}")
        except Exception:
            pass
def _ensure_match_source_cols() -> None:
    """Add source-ingestion provenance without rewriting legacy match rows."""
    if env.MODE == "sqlite":
        cols = [r[1] for r in run_query("PRAGMA table_info(matches)")]
        if "source_ingested_at" not in cols:
            run_exec("ALTER TABLE matches ADD COLUMN source_ingested_at TEXT")
    else:
        run_exec("ALTER TABLE matches ADD COLUMN IF NOT EXISTS source_ingested_at TEXT")
def _ensure_prediction_updated_at() -> None:
    """Backfill-less ALTER: SQLite forbids non-constant defaults here, so the
    column is nullable and only future UPDATEs populate it."""
    try:
        if env.MODE == "sqlite":
            cols = [r[1] for r in run_query("PRAGMA table_info(predictions)")]
            if "updated_at" not in cols:
                run_exec("ALTER TABLE predictions ADD COLUMN updated_at TEXT")
        else:
            run_exec("ALTER TABLE predictions ADD COLUMN IF NOT EXISTS updated_at TEXT")
    except Exception:
        pass
def _ensure_league_model_cols() -> None:
    """Add the dynamic league_models columns used by explicit projections."""
    for col, decl in (("rho", "REAL DEFAULT 0.0"),
                      ("bayesian", "INTEGER DEFAULT 0"),
                      ("method", "TEXT DEFAULT 'poisson'"),
                      ("ctx_rest", "INTEGER DEFAULT 0"),
                      ("ctx_form", "INTEGER DEFAULT 0"),
                      ("ctx_team_ha", "INTEGER DEFAULT 0")):
        try:
            if env.MODE == "sqlite":
                cols = [r[1] for r in run_query("PRAGMA table_info(league_models)")]
                if col not in cols:
                    run_exec(f"ALTER TABLE league_models ADD COLUMN {col} {decl}")
            else:
                run_exec(f"ALTER TABLE league_models ADD COLUMN IF NOT EXISTS {col} {decl}")
        except Exception:
            pass
def _record_migration(version: str) -> None:
    if env.MODE == "sqlite":
        run_exec("INSERT OR IGNORE INTO schema_migrations(version) VALUES(?)", (version,))
    else:
        run_exec("INSERT INTO schema_migrations(version) VALUES(?) ON CONFLICT DO NOTHING", (version,))
def _ensure_user_cols() -> None:
    """Ensure role + is_active on users for DBs created before Phase 1/2."""
    try:
        if env.MODE == "sqlite":
            cols = [r[1] for r in run_query("PRAGMA table_info(users)")]
            if "role" not in cols:
                run_exec("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
            if "is_active" not in cols:
                run_exec("ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")
            # allow existing NULL is_active rows to be treated as active
            run_exec("UPDATE users SET is_active=1 WHERE is_active IS NULL")
            duplicates = run_query(
                "SELECT LOWER(username) normalized, COUNT(*) c FROM users "
                "GROUP BY LOWER(username) HAVING COUNT(*) > 1")
            if duplicates:
                raise RuntimeError("Cannot enforce case-insensitive usernames: duplicate existing users")
        else:
            run_exec("ALTER TABLE users ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'user'")
            run_exec("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active INTEGER NOT NULL DEFAULT 1")
        duplicates = run_query(
            "SELECT LOWER(username) normalized, COUNT(*) c FROM users "
            "GROUP BY LOWER(username) HAVING COUNT(*) > 1")
        if duplicates:
            raise RuntimeError("Cannot enforce case-insensitive usernames: duplicate existing users")
        # Authentication normalizes usernames to lowercase. Bring legacy rows
        # into that same canonical representation before adding the index.
        run_exec("UPDATE users SET username=LOWER(username) WHERE username<>LOWER(username)")
        run_exec("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username_ci ON users(LOWER(username))")
    except Exception:
        raise
def _ensure_job_cols() -> None:
    try:
        if env.MODE == "sqlite":
            cols = [r[1] for r in run_query("PRAGMA table_info(jobs)")]
            if "lease_expires_at" not in cols:
                run_exec("ALTER TABLE jobs ADD COLUMN lease_expires_at TEXT")
            run_exec("CREATE TABLE IF NOT EXISTS workers (worker_id TEXT PRIMARY KEY, started_at TEXT NOT NULL, last_heartbeat_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'online')")
            run_exec("CREATE INDEX IF NOT EXISTS idx_workers_heartbeat ON workers(last_heartbeat_at)")
        else:
            run_exec("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS lease_expires_at TEXT")
            run_exec("CREATE TABLE IF NOT EXISTS workers (worker_id TEXT PRIMARY KEY, started_at TEXT NOT NULL, last_heartbeat_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'online')")
            run_exec("CREATE INDEX IF NOT EXISTS idx_workers_heartbeat ON workers(last_heartbeat_at)")
    except Exception:
        raise
def _ensure_execution_events() -> None:
    """Create the append-only execution ledger for databases predating Phase 6."""
    if env.MODE == "sqlite":
        run_exec(
            "CREATE TABLE IF NOT EXISTS execution_events ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, execution_id TEXT NOT NULL, "
            "execution_type TEXT NOT NULL, event_type TEXT NOT NULL CHECK(event_type IN ('started', 'finished')), "
            "status TEXT NOT NULL, ts TEXT NOT NULL, snapshot_hash TEXT NOT NULL, "
            "parameters TEXT NOT NULL, artifact_content_hash TEXT, results TEXT, "
            "created_at TEXT NOT NULL DEFAULT (datetime('now')))"
        )
    else:
        run_exec(
            "CREATE TABLE IF NOT EXISTS execution_events ("
            "id SERIAL PRIMARY KEY, execution_id TEXT NOT NULL, execution_type TEXT NOT NULL, "
            "event_type TEXT NOT NULL CHECK(event_type IN ('started', 'finished')), "
            "status TEXT NOT NULL, ts TEXT NOT NULL, snapshot_hash TEXT NOT NULL, "
            "parameters TEXT NOT NULL, artifact_content_hash TEXT, results TEXT, "
            "created_at TEXT NOT NULL DEFAULT (datetime('now')))"
        )
    run_exec("CREATE INDEX IF NOT EXISTS idx_execution_events_execution ON execution_events(execution_id, id)")
    run_exec("CREATE INDEX IF NOT EXISTS idx_execution_events_type ON execution_events(execution_type, id)")
