"""Camada de banco dual-engine do AP2WEB.

- SQLite (padrão local): comportamento idêntico ao original.
- Postgres (Neon/Supabase etc.): ativado pela env var DATABASE_URL.
  O SQL escrito no projeto continua em dialeto SQLite (`?`, date(),
  datetime('now')) — a camada traduz em tempo de execução (ML Skill v1.1 §20.1:
  fonte única; nenhuma query paralela por engine).
"""
from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
MODE = "postgres" if DATABASE_URL else "sqlite"

DB_PATH = Path(os.environ.get(
    "AP2WEB_DB_PATH",
    Path(__file__).resolve().parent.parent / "ap2web.db"))

if MODE == "postgres":
    import psycopg  # psycopg 3
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool
    _pool = ConnectionPool(DATABASE_URL, min_size=2, max_size=10, kwargs={"row_factory": dict_row})

# ─────────────────────────────────────────────────────────────────────────────
# Tradução SQLite -> Postgres
# ─────────────────────────────────────────────────────────────────────────────

def _to_pg_sql(sql: str) -> str:
    """Traduz dialeto SQLite para Postgres.

    - placeholders ? -> %s
    - date(expr)     -> (expr)::date        (evita 'match_date' via \b)
    - date(?)        -> (left(?,10))::date  (PG é estrito com formato de data)
    - datetime('now')-> to_char(now(),...)
    - window         -> "window"            (palavra reservada no PG)
    """
    # 1) params dentro de date(): trunca para YYYY-MM-DD antes do cast
    s = re.sub(r"\bdate\(\s*\?\s*\)", "(left(?,10))::date", s := sql)
    # 2) placeholders ? -> %s
    s = s.replace("?", "%s")
    # 3) colunas: date(expr) -> (expr)::date
    s = re.sub(r"\bdate\(([^()]+)\)", r"(\1)::date", s)
    # 4) datetime('now')
    s = s.replace("datetime('now')",
                  "to_char(now(), 'YYYY-MM-DD HH24:MI:SS')")
    # 5) palavra reservada
    s = re.sub(r'\bwindow\b', '"window"', s)
    return s


def _pg_connect():
    """Retorna conexão do pool (context manager compatível)."""
    return _pool.connection()


# ─────────────────────────────────────────────────────────────────────────────
# Schema
# ─────────────────────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'user',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS leagues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sofascore_id INTEGER UNIQUE NOT NULL,   -- unique-tournament id do Sofascore
    name TEXT NOT NULL,
    country TEXT,
    season_id INTEGER,                      -- temporada ativa no Sofascore
    season_name TEXT,
    last_sync TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    league_id INTEGER NOT NULL REFERENCES leagues(id) ON DELETE CASCADE,
    sofascore_id INTEGER,                   -- id do time no Sofascore
    name TEXT NOT NULL,
    UNIQUE(league_id, sofascore_id)
);

CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    league_id INTEGER NOT NULL REFERENCES leagues(id) ON DELETE CASCADE,
    sofascore_id INTEGER UNIQUE,            -- event id do Sofascore
    home_team_id INTEGER REFERENCES teams(id),
    away_team_id INTEGER REFERENCES teams(id),
    kickoff_datetime TEXT,                  -- kickoff em UTC (ISO 8601), fonte: Sofascore startTimestamp
    match_date TEXT,                        -- derived date (YYYY-MM-DD) for backward compat
    round INTEGER,
    status TEXT,                            -- played | scheduled
    score_home INTEGER,
    score_away INTEGER,
    -- estatísticas do Sofascore (casa / fora)
    xg_home REAL, xg_away REAL,
    xg_on_target_home REAL, xg_on_target_away REAL,
    possession_home REAL, possession_away REAL,
    shots_total_home REAL, shots_total_away REAL,
    shots_on_target_home REAL, shots_on_target_away REAL,
    shots_off_target_home REAL, shots_off_target_away REAL,
    shots_inside_box_home REAL, shots_inside_box_away REAL,
    shots_outside_box_home REAL, shots_outside_box_away REAL,
    blocked_shots_home REAL, blocked_shots_away REAL,
    big_chances_home REAL, big_chances_away REAL,
    big_chances_missed_home REAL, big_chances_missed_away REAL,
    corners_home REAL, corners_away REAL,
    fouls_home REAL, fouls_away REAL,
    yellow_cards_home REAL, yellow_cards_away REAL,
    red_cards_home REAL, red_cards_away REAL,
    passes_home REAL, passes_away REAL,
    accurate_passes_home REAL, accurate_passes_away REAL,
    offsides_home REAL, offsides_away REAL,
    saves_home REAL, saves_away REAL,
    interceptions_home REAL, interceptions_away REAL,
    recoveries_home REAL, recoveries_away REAL,
    tackles_home REAL, tackles_away REAL,
    dribbles_home REAL, dribbles_away REAL,
    duels_home REAL, duels_away REAL,
    aerial_duels_home REAL, aerial_duels_away REAL,
    final_third_home REAL, final_third_away REAL,
    throw_ins_home REAL, throw_ins_away REAL,
    goal_kicks_home REAL, goal_kicks_away REAL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(league_id, sofascore_id)
);

CREATE INDEX IF NOT EXISTS idx_matches_league ON matches(league_id);
CREATE INDEX IF NOT EXISTS idx_matches_kickoff ON matches(kickoff_datetime);
CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(match_date);
CREATE INDEX IF NOT EXISTS idx_matches_status ON matches(status);
CREATE INDEX IF NOT EXISTS idx_matches_home_team ON matches(home_team_id);
CREATE INDEX IF NOT EXISTS idx_matches_away_team ON matches(away_team_id);
CREATE INDEX IF NOT EXISTS idx_matches_league_status ON matches(league_id, status);
CREATE INDEX IF NOT EXISTS idx_matches_league_kickoff ON matches(league_id, kickoff_datetime);
CREATE INDEX IF NOT EXISTS idx_matches_status_kickoff ON matches(status, kickoff_datetime);

CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    league_id INTEGER,
    match_id INTEGER,
    home_team_id INTEGER,
    away_team_id INTEGER,
    home_name TEXT,
    away_name TEXT,
    match_date TEXT,
    pick_type TEXT,                  -- 1X2 | GOLS | BTTS | PLACAR
    pick_value TEXT,                 -- "1"|"X"|"2", "over_2.5", "sim", "2-1"
    pick_label TEXT,
    prob REAL,
    odd REAL,
    payload TEXT,                    -- JSON com a previsão completa
    model_version TEXT,
    model_method TEXT,
    feature_version TEXT,
    data_snapshot_timestamp TEXT,
    as_of_timestamp TEXT,
    training_window INTEGER,
    training_sample_size INTEGER,
    league_model_version TEXT,
    predicted_at TEXT,
    source_data_freshness TEXT,
    confidence_level TEXT,
    fallback_reason TEXT,
    brier_score REAL,
    log_loss REAL,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending | correct | wrong
    resolved_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_predictions_status ON predictions(status);
CREATE INDEX IF NOT EXISTS idx_predictions_match ON predictions(match_id);
CREATE INDEX IF NOT EXISTS idx_predictions_user ON predictions(user_id);
CREATE INDEX IF NOT EXISTS idx_predictions_user_status ON predictions(user_id, status);
CREATE INDEX IF NOT EXISTS idx_predictions_league ON predictions(league_id);

CREATE TABLE IF NOT EXISTS league_models (
    league_id INTEGER PRIMARY KEY REFERENCES leagues(id) ON DELETE CASCADE,
    home_advantage REAL NOT NULL DEFAULT 1.15,   -- fator de mando calibrado por liga
    window INTEGER NOT NULL DEFAULT 10,          -- janela deslizante ótima (últimos N jogos)
    feature TEXT NOT NULL DEFAULT 'xg',          -- xg | goals | blend
    accuracy REAL,                               -- acurácia 1X2 no backtest (0-100)
    brier REAL,                                  -- Brier score (menor = melhor)
    sample_count INTEGER,                        -- nº de jogos usados no backtest
    calibrated_at TEXT,
    bayesian INTEGER DEFAULT 0,                  -- 1 = usa Engine Bayesiano (FASE 13)
    method TEXT DEFAULT 'poisson'                -- poisson | bayesian | hybrid
);

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_teams_league ON teams(league_id);
CREATE INDEX IF NOT EXISTS idx_teams_league_sofascore ON teams(league_id, sofascore_id);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_type TEXT NOT NULL,             -- sync_all | sync_league | calibrate_all | calibrate_league | backtest | promotion
    status TEXT NOT NULL DEFAULT 'pending', -- pending | running | completed | failed | cancelled
    requested_by INTEGER REFERENCES users(id),
    league_id INTEGER REFERENCES leagues(id),
    parameters TEXT,                    -- JSON
    idempotency_key TEXT UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    started_at TEXT,
    finished_at TEXT,
    cancelled_at TEXT,
    progress REAL DEFAULT 0,
    result TEXT,                        -- JSON
    error_message TEXT,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    worker_id TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_type_status ON jobs(job_type, status);
CREATE INDEX IF NOT EXISTS idx_jobs_idempotency ON jobs(idempotency_key);
CREATE INDEX IF NOT EXISTS idx_jobs_requested_by ON jobs(requested_by);

CREATE TABLE IF NOT EXISTS workers (
    worker_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    last_heartbeat_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'online'
);
CREATE INDEX IF NOT EXISTS idx_workers_heartbeat ON workers(last_heartbeat_at);

CREATE TABLE IF NOT EXISTS auth_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    access_jti TEXT NOT NULL DEFAULT '',
    refresh_token_hash TEXT NOT NULL,
    family_id TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked_at TEXT,
    revoked_reason TEXT,
    ip_address TEXT,
    user_agent TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_used_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_user ON auth_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_refresh_hash ON auth_sessions(refresh_token_hash);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_family ON auth_sessions(family_id);

CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,
    ts TEXT NOT NULL,
    request_id TEXT,
    user_id INTEGER,
    username TEXT,
    role TEXT,
    action TEXT NOT NULL,
    resource_type TEXT,
    resource_id TEXT,
    source_ip TEXT,
    user_agent TEXT,
    success INTEGER NOT NULL DEFAULT 1,
    error_code TEXT,
    metadata TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_events(ts);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_events(action);
CREATE INDEX IF NOT EXISTS idx_audit_username ON audit_events(username);
"""

_PG_SCHEMA = re.sub(
    r"\bdate\(([^()]+)\)", r"(\1)::date",
    SCHEMA.replace("INTEGER PRIMARY KEY AUTOINCREMENT",
                   "SERIAL PRIMARY KEY")
          .replace("datetime('now')",
                   "to_char(now(), 'YYYY-MM-DD HH24:MI:SS')")
          .replace(" window INTEGER", ' "window" INTEGER'))

# ─────────────────────────────────────────────────────────────────────────────
# API pública (mesma assinatura das duas engines)
# ─────────────────────────────────────────────────────────────────────────────

def get_conn() -> sqlite3.Connection:
    """SQLite apenas. Em modo Postgres, use run_query/run_exec."""
    conn = sqlite3.connect(DB_PATH, timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=60000")
    return conn


def _ensure_provenance_cols():
    for col, typ in [("model_method","TEXT"),("feature_version","TEXT"),("data_snapshot_timestamp","TEXT"),
                     ("as_of_timestamp","TEXT"),("training_window","INTEGER"),("training_sample_size","INTEGER"),
                     ("league_model_version","TEXT"),("source_data_freshness","TEXT"),("confidence_level","TEXT"),("fallback_reason","TEXT")]:
        try:
            if MODE=="sqlite":
                cols=[r[1] for r in run_query("PRAGMA table_info(predictions)")]
                if col not in cols:
                    run_exec(f"ALTER TABLE predictions ADD COLUMN {col} {typ}")
            else:
                run_exec(f"ALTER TABLE predictions ADD COLUMN IF NOT EXISTS {col} {typ}")
        except Exception:
            pass

def _ensure_user_cols() -> None:
    """Ensure role + is_active on users for DBs created before Phase 1/2."""
    try:
        if MODE == "sqlite":
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
        if MODE == "sqlite":
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


def init_db() -> None:
    if MODE == "sqlite":
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
        return
    with _pg_connect() as conn:
        for stmt in _PG_SCHEMA.split(";"):
            if stmt.strip():
                conn.execute(stmt)
        try:
            conn.execute("INSERT INTO schema_migrations(version) VALUES(%s) ON CONFLICT DO NOTHING", ("20260909_baseline",))
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
        # pg provenance ensure
        _ensure_provenance_cols()
        _ensure_user_cols()
        _ensure_job_cols()


def _seed_leagues(conn: sqlite3.Connection) -> None:
    """Insere ligas do leagues_config.py se a tabela estiver vazia."""
    count = conn.execute("SELECT COUNT(*) FROM leagues").fetchone()[0]
    if count > 0:
        return
    try:
        from .leagues_config import LEAGUES
    except ImportError:
        return
    for lg in LEAGUES:
        conn.execute(
            "INSERT OR IGNORE INTO leagues(sofascore_id, name, country) VALUES(?,?,?)",
            (lg["id"], lg["name"], lg["country"]))
    conn.commit()


def reset_db() -> None:
    """Remove todas as tabelas e recria (banco novo do zero)."""
    if MODE == "sqlite":
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


def run_query(query: str, params: tuple = ()) -> list[dict]:
    """SELECT — retorna linhas acessíveis por r["coluna"]."""
    if MODE == "sqlite":
        conn = get_conn()
        try:
            return conn.execute(query, params).fetchall()
        finally:
            conn.close()
    with _pg_connect() as conn:
        return conn.execute(_to_pg_sql(query), params).fetchall()


def run_exec(query: str, params: tuple = ()) -> int:
    """INSERT/UPDATE/DELETE — retorna id (INSERT) ou rowcount (UPDATE/DELETE).

    Em Postgres, INSERTs em tabelas com chave numérica ``id`` ganham RETURNING
    id para preservar o contrato lastrowid usado pelo restante do código.
    """
    if MODE == "sqlite":
        conn = get_conn()
        try:
            cur = conn.execute(query, params)
            conn.commit()
            if query.lstrip().upper().startswith("INSERT"):
                return cur.lastrowid if cur.lastrowid is not None else 0
            return cur.rowcount
        finally:
            conn.close()
    q = _to_pg_sql(query)
    returns_id = _insert_returns_id(q)
    if returns_id:
        q += " RETURNING id"
    with _pg_connect() as conn:
        return _pg_exec(conn, q, params, returns_id)


def _insert_returns_id(query: str) -> bool:
    """Only tables with an integer ``id`` may use PostgreSQL RETURNING id."""
    match = re.match(r'\s*INSERT(?:\s+OR\s+\w+)?\s+INTO\s+"?([a-z_]+)', query, re.I)
    return bool(match and "RETURNING" not in query.upper() and match.group(1).lower() in {
        "users", "leagues", "teams", "matches", "predictions", "jobs",
        "auth_sessions", "audit_events",
    })


def _pg_exec(conn, q: str, params: tuple, returns_id: bool) -> int:
    """Executa com RETURNING id; se a tabela não tiver coluna id, cai para rowcount."""
    try:
        cur = conn.execute(q, params)
        row = cur.fetchone() if returns_id else None
        conn.commit()
        return row["id"] if row else cur.rowcount
    except psycopg.errors.UndefinedColumn:
        conn.rollback()
        if not returns_id:
            raise
        cur = conn.execute(q.replace(" RETURNING id", ""), params)
        conn.commit()
        return cur.rowcount
