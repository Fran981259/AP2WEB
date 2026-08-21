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
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


# ─────────────────────────────────────────────────────────────────────────────
# Schema
# ─────────────────────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
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
    predicted_at TEXT,
    brier_score REAL,
    log_loss REAL,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending | correct | wrong
    resolved_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_predictions_status ON predictions(status);
CREATE INDEX IF NOT EXISTS idx_predictions_match ON predictions(match_id);

CREATE TABLE IF NOT EXISTS league_models (
    league_id INTEGER PRIMARY KEY REFERENCES leagues(id) ON DELETE CASCADE,
    home_advantage REAL NOT NULL DEFAULT 1.15,   -- fator de mando calibrado por liga
    window INTEGER NOT NULL DEFAULT 10,          -- janela deslizante ótima (últimos N jogos)
    feature TEXT NOT NULL DEFAULT 'xg',          -- xg | goals | blend
    accuracy REAL,                               -- acurácia 1X2 no backtest (0-100)
    brier REAL,                                  -- Brier score (menor = melhor)
    sample_count INTEGER,                        -- nº de jogos usados no backtest
    calibrated_at TEXT
);
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


def init_db() -> None:
    if MODE == "sqlite":
        conn = get_conn()
        try:
            conn.executescript(SCHEMA)
            conn.commit()
        finally:
            conn.close()
        return
    with _pg_connect() as conn:
        for stmt in _PG_SCHEMA.split(";"):
            if stmt.strip():
                conn.execute(stmt)


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

    Em Postgres, INSERT ganha RETURNING id automaticamente para preservar
    o contrato lastrowid usado pelo restante do código.
    """
    if MODE == "sqlite":
        conn = get_conn()
        try:
            cur = conn.execute(query, params)
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()
    q = _to_pg_sql(query)
    stripped = q.lstrip().upper()
    returns_id = stripped.startswith("INSERT") and "RETURNING" not in stripped.upper()
    if returns_id:
        q += " RETURNING id"
    with _pg_connect() as conn:
        return _pg_exec(conn, q, params, returns_id)


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
