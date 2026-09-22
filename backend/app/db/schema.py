"""Canonical SQLite DDL for the AP2WEB database (single source of truth)."""
from __future__ import annotations


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
    source_ingested_at TEXT,                -- UTC time this source record was fetched/ingested
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
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_predictions_status ON predictions(status);
CREATE INDEX IF NOT EXISTS idx_predictions_match ON predictions(match_id);
CREATE INDEX IF NOT EXISTS idx_predictions_user ON predictions(user_id);
CREATE INDEX IF NOT EXISTS idx_predictions_user_status ON predictions(user_id, status);
CREATE INDEX IF NOT EXISTS idx_predictions_league ON predictions(league_id);
CREATE INDEX IF NOT EXISTS idx_predictions_home_team ON predictions(home_team_id);
CREATE INDEX IF NOT EXISTS idx_predictions_away_team ON predictions(away_team_id);

CREATE TABLE IF NOT EXISTS odds_quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    market_type TEXT NOT NULL,
    outcome TEXT NOT NULL,
    decimal_odd REAL NOT NULL,
    provider TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    source_ingested_at TEXT NOT NULL DEFAULT (datetime('now')),
    source_event_id TEXT,
    UNIQUE(match_id, market_type, outcome, provider, captured_at)
);
CREATE INDEX IF NOT EXISTS idx_odds_quotes_asof
    ON odds_quotes(match_id, market_type, captured_at);

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
    method TEXT DEFAULT 'poisson',               -- poisson | bayesian | hybrid
    rho REAL DEFAULT 0.0,                        -- Dixon-Coles dependency
    ctx_rest INTEGER DEFAULT 0,                  -- context feature flags (FASE 14)
    ctx_form INTEGER DEFAULT 0,
    ctx_team_ha INTEGER DEFAULT 0
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
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    lease_expires_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_type_status ON jobs(job_type, status);
CREATE INDEX IF NOT EXISTS idx_jobs_idempotency ON jobs(idempotency_key);
CREATE INDEX IF NOT EXISTS idx_jobs_requested_by ON jobs(requested_by);
CREATE INDEX IF NOT EXISTS idx_jobs_league ON jobs(league_id);

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
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_events(user_id);

CREATE TABLE IF NOT EXISTS execution_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_id TEXT NOT NULL,
    execution_type TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK(event_type IN ('started', 'finished')),
    status TEXT NOT NULL,
    ts TEXT NOT NULL,
    snapshot_hash TEXT NOT NULL,
    parameters TEXT NOT NULL,
    artifact_content_hash TEXT,
    results TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_execution_events_execution ON execution_events(execution_id, id);
CREATE INDEX IF NOT EXISTS idx_execution_events_type ON execution_events(execution_type, id);
"""
