"""Listas explícitas de colunas — fonte única para projeções SQL.

O projeto proíbe ``SELECT *`` (GOLDCODE): listas explícitas tornam o contrato
de cada query estável frente a ``ALTER TABLE`` e evitam transportar colunas
que o chamador não usa. Mantenha cada lista em sincronia com ``db.SCHEMA``.
"""
from __future__ import annotations

USERS = (
    "id, username, password_hash, role, is_active, created_at"
)

LEAGUES = (
    "id, sofascore_id, name, country, season_id, season_name, last_sync, created_at"
)

TEAMS = "id, league_id, sofascore_id, name"

MATCHES = (
    "id, league_id, sofascore_id, home_team_id, away_team_id, kickoff_datetime, "
    "match_date, round, status, score_home, score_away, "
    "xg_home, xg_away, xg_on_target_home, xg_on_target_away, "
    "possession_home, possession_away, shots_total_home, shots_total_away, "
    "shots_on_target_home, shots_on_target_away, shots_off_target_home, "
    "shots_off_target_away, shots_inside_box_home, shots_inside_box_away, "
    "shots_outside_box_home, shots_outside_box_away, blocked_shots_home, "
    "blocked_shots_away, big_chances_home, big_chances_away, "
    "big_chances_missed_home, big_chances_missed_away, corners_home, corners_away, "
    "fouls_home, fouls_away, yellow_cards_home, yellow_cards_away, "
    "red_cards_home, red_cards_away, passes_home, passes_away, "
    "accurate_passes_home, accurate_passes_away, offsides_home, offsides_away, "
    "saves_home, saves_away, interceptions_home, interceptions_away, "
    "recoveries_home, recoveries_away, tackles_home, tackles_away, "
    "dribbles_home, dribbles_away, duels_home, duels_away, "
    "aerial_duels_home, aerial_duels_away, final_third_home, final_third_away, "
    "throw_ins_home, throw_ins_away, goal_kicks_home, goal_kicks_away, "
    "source_ingested_at, created_at"
)

PREDICTIONS = (
    "id, user_id, league_id, match_id, home_team_id, away_team_id, home_name, "
    "away_name, match_date, pick_type, pick_value, pick_label, prob, odd, payload, "
    "model_version, model_method, feature_version, data_snapshot_timestamp, "
    "as_of_timestamp, training_window, training_sample_size, league_model_version, "
    "predicted_at, source_data_freshness, confidence_level, fallback_reason, "
    "brier_score, log_loss, status, resolved_at, created_at, updated_at"
)

ODDS_QUOTES = (
    "id, match_id, market_type, outcome, decimal_odd, provider, captured_at, "
    "source_ingested_at, source_event_id"
)

# rho / ctx_* são adicionados por migração leve (ver db._ensure_league_model_cols).
LEAGUE_MODELS = (
    "league_id, home_advantage, window, feature, accuracy, brier, sample_count, "
    "calibrated_at, bayesian, method, rho, ctx_rest, ctx_form, ctx_team_ha"
)

JOBS = (
    "id, job_type, status, requested_by, league_id, parameters, idempotency_key, "
    "created_at, started_at, finished_at, cancelled_at, progress, result, "
    "error_message, attempt_count, worker_id, updated_at, lease_expires_at"
)

WORKERS = "worker_id, started_at, last_heartbeat_at, status"

AUTH_SESSIONS = (
    "id, user_id, access_jti, refresh_token_hash, family_id, expires_at, "
    "revoked_at, revoked_reason, ip_address, user_agent, created_at, last_used_at"
)

AUDIT_EVENTS = (
    "id, event_id, ts, request_id, user_id, username, role, action, "
    "resource_type, resource_id, source_ip, user_agent, success, error_code, "
    "metadata, created_at"
)

EXECUTION_EVENTS = (
    "id, execution_id, execution_type, event_type, status, ts, snapshot_hash, "
    "parameters, artifact_content_hash, results, created_at"
)


def prefixed(cols: str, alias: str) -> str:
    """Aplica o alias de tabela a uma lista de colunas separada por vírgula."""
    return ", ".join(f"{alias}.{name.strip()}" for name in cols.split(","))
