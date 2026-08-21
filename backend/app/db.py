"""Banco de dados SQLite — schema do AP2WEB (fonte única: Sofascore)."""
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


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=60000")
    return conn


def init_db() -> None:
    conn = get_conn()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def reset_db() -> None:
    """Remove todas as tabelas e recria (banco novo do zero)."""
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