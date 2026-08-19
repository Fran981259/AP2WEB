"""Banco de dados SQLite — schema do AP2WEB."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

DB_PATH = Path(os.environ.get(
    "AP2WEB_DB_PATH",
    Path(__file__).resolve().parent.parent / "ap2web.db"))

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS leagues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,          -- slug usado pelo soccerstats (ex: england)
    name TEXT NOT NULL,
    country TEXT,
    season TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    league_id INTEGER NOT NULL REFERENCES leagues(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    stats_key TEXT,                     -- id de time no soccerstats (ex: stats=1-aldosivi)
    UNIQUE(league_id, name)
);

CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    league_id INTEGER NOT NULL REFERENCES leagues(id) ON DELETE CASCADE,
    home_team_id INTEGER REFERENCES teams(id),
    away_team_id INTEGER REFERENCES teams(id),
    match_date TEXT,
    kickoff TEXT,
    status TEXT,                        -- scheduled | played
    ht_home INTEGER, ht_away INTEGER,
    ft_home INTEGER, ft_away INTEGER,
    corners_home INTEGER, corners_away INTEGER,
    source_url TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(league_id, home_team_id, away_team_id, match_date)
);

CREATE TABLE IF NOT EXISTS team_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    scope TEXT,                         -- home | away
    gp INTEGER, win_pct REAL, fts_pct REAL, cs_pct REAL, bts_pct REAL,
    tg REAL, gf REAL, ga REAL,
    ov15 REAL, ov25 REAL, ov35 REAL, ppg REAL,
    UNIQUE(match_id, team_id)
);

CREATE TABLE IF NOT EXISTS scrape_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at TEXT,
    source TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',  -- running | ok | error
    leagues_updated INTEGER NOT NULL DEFAULT 0,
    matches_found INTEGER NOT NULL DEFAULT 0,
    matches_saved INTEGER NOT NULL DEFAULT 0,
    error TEXT
);

CREATE TABLE IF NOT EXISTS scrape_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES scrape_runs(id) ON DELETE CASCADE,
    league TEXT,
    message TEXT,
    level TEXT NOT NULL DEFAULT 'info',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

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
    pick_label TEXT,                 -- ex "Back Real Madrid", "Over 2.5"
    prob REAL,
    odd REAL,
    payload TEXT,                    -- JSON com a previsão completa
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
    accuracy REAL,                               -- acurácia 1X2 no backtest (0-100)
    brier REAL,                                  -- Brier score (menor = melhor)
    sample_count INTEGER,                        -- nº de jogos usados no backtest
    calibrated_at TEXT
);
"""


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    conn = get_conn()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def run_query(query: str, params: tuple = ()) -> list[sqlite3.Row]:
    conn = get_conn()
    try:
        return conn.execute(query, params).fetchall()
    finally:
        conn.close()


def run_exec(query: str, params: tuple = ()) -> int:
    conn = get_conn()
    try:
        cur = conn.execute(query, params)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()