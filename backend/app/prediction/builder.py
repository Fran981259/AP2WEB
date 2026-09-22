"""Prediction builder: assembles the full match/fixture response."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from .. import db
from ..bayesian import bayesian_lambda_blend
from ..learning import get_model
from ..model import MatchInput, TeamInput, predict as run_predict
from .bayesian import (
    _avg_stats_bayesian,
    _run_bayesian_predict,
    _should_use_bayesian,
    _with_posterior_means,
)
from .context import _apply_context, _context_flags, _kickoff_ts
from .history import (
    _avg_stats,
    _avg_stats_detail,
    _compare,
    _h2h,
    _recent_form,
)
from .settings import FEATURE_VERSION, MODEL_CODE_VERSION, _log


def _model_for(league_id: int) -> dict:
    return get_model(league_id)
def _build(league_id: int, home_team_id: int, away_team_id: int,
           home_name: str, away_name: str, league_name: str,
           match: dict | None = None, as_of_timestamp: str | None = None,
           use_bayesian: bool | None = None) -> dict:
    model = _model_for(league_id)
    feature = model["feature"]
    window = model["window"]
    home_stats = _avg_stats(league_id, home_team_id, window, feature, as_of_timestamp)
    away_stats = _avg_stats(league_id, away_team_id, window, feature, as_of_timestamp)
    home_detail = _avg_stats_detail(league_id, home_team_id, window, feature, as_of_timestamp)
    away_detail = _avg_stats_detail(league_id, away_team_id, window, feature, as_of_timestamp)

    mi = MatchInput(
        league=league_name,
        home=TeamInput(name=home_name, **home_stats),
        away=TeamInput(name=away_name, **away_stats),
    )
    result = run_predict(mi, home_advantage=model["home_advantage"],
                         rho=model.get("rho", 0.0))

    base_match = {
        "id": None,
        "league": league_name,
        "league_id": league_id,
        "date": None,
        "kickoff": None,
        "home": home_name,
        "home_id": home_team_id,
        "away": away_name,
        "away_id": away_team_id,
    }
    if match:
        match = dict(match)
        kd = match.get("kickoff_datetime") or match.get("match_date")
        base_match.update({
            "id": match["id"],
            "date": kd[:10] if kd else None,
            "round": match.get("round"),
        })

    # Provenance freshness is when source data entered this system, not when a
    # historical fixture happened. Legacy rows fall back to the durable league sync.
    try:
        snap_row = db.run_query(
            "SELECT COALESCE(MAX(source_ingested_at), "
            "(SELECT last_sync FROM leagues WHERE id=?)) m FROM matches WHERE league_id=?",
            (league_id, league_id))
        data_snapshot = snap_row[0]["m"] if snap_row and snap_row[0]["m"] else None
    except Exception:
        data_snapshot = None
    try:
        prov_str = f"{MODEL_CODE_VERSION}|{FEATURE_VERSION}|{model.get('feature')}|{model.get('window')}|{model.get('home_advantage')}|{model.get('rho')}|{model.get('method')}|{model.get('calibrated_at')}"
        model_version = hashlib.sha256(prov_str.encode()).hexdigest()[:12]
    except Exception:
        model_version = MODEL_CODE_VERSION
    # confidence based on sample size
    sample_n = model.get("sample_count") or 0
    total_games = (home_detail.get("count",0)+away_detail.get("count",0))
    if total_games < 5 or sample_n < 20:
        confidence_level = "low"
        fallback_reason = "insufficient_history"
    elif total_games < 10:
        confidence_level = "medium"
        fallback_reason = None
    else:
        confidence_level = "high"
        fallback_reason = None
    provenance = {
        "model_version": model_version,
        "model_method": model.get("method","poisson"),
        "feature_version": FEATURE_VERSION,
        "data_snapshot_timestamp": data_snapshot,
        "as_of_timestamp": as_of_timestamp,
        "training_window": window,
        "training_sample_size": sample_n,
        "league_model_version": model.get("calibrated_at"),
        "prediction_created_at": datetime.now(timezone.utc).isoformat(),
        "source_data_freshness": data_snapshot,
        "confidence_level": confidence_level,
        "fallback_reason": fallback_reason,
    }
    _log.debug("pred provenance league=%s model=%s snap=%s conf=%s", league_id, model_version, data_snapshot, confidence_level)

    response = {
        "match": base_match,
        "provenance": provenance,
        "model_version": model_version,
        "feature_version": FEATURE_VERSION,
        "data_snapshot_timestamp": data_snapshot,
        "confidence_level": confidence_level,
        "lambdas": result.lambdas,
        "probs": result.probs,
        "top_scores": result.top_scores,
        "proposals": result.proposals,
        "inputs": {"home": home_stats, "away": away_stats},
        "compare": _compare(league_id, home_team_id, away_team_id,
                            home_name, away_name, home_stats, away_stats, feature,
                            as_of_timestamp),
        "model": {"home_advantage": model["home_advantage"], "window": model["window"],
                  "feature": feature, "rho": model.get("rho", 0.0),
                  "model_type": result.model_type,
                  "method": model.get("method", "poisson"),
                  "bayesian": int(model.get("bayesian", 0)),
                  "accuracy": model.get("accuracy"),
                  "brier": model.get("brier"),
                  "model_version": model_version,
                  "feature_version": FEATURE_VERSION},
        "data": {
            "source": f"sofascore_{feature}",
            "home": {"name": home_name, "avg": home_stats, **home_detail},
            "away": {"name": away_name, "avg": away_stats, **away_detail},
            "form": {"home": _recent_form(league_id, home_team_id,
                                          as_of_timestamp=as_of_timestamp),
                     "away": _recent_form(league_id, away_team_id,
                                          as_of_timestamp=as_of_timestamp)},
            "h2h": _h2h(league_id, home_team_id, away_team_id, limit=10,
                        as_of_timestamp=as_of_timestamp),
            "model": {"home_advantage": model["home_advantage"], "window": model["window"],
                      "feature": feature, "rho": model.get("rho", 0.0),
                      "model_type": result.model_type,
                      "accuracy": model.get("accuracy"),
                      "brier": model.get("brier")},
        },
    }

    # Bayesian and hybrid consume the same selected feature as the Poisson path.
    oper = result
    model_method = model.get("method", "poisson")
    if _should_use_bayesian(model_method, use_bayesian):
        bay_home = _avg_stats_bayesian(league_id, home_team_id, window, feature, as_of_timestamp)
        bay_away = _avg_stats_bayesian(league_id, away_team_id, window, feature, as_of_timestamp)

        if model_method in ("bayesian", "hybrid"):
            if model_method == "hybrid":
                mix_h = bayesian_lambda_blend(
                    bay_home["gf_avg"], bay_home["ga_avg"],
                    home_stats["gf_avg"], home_stats["ga_avg"],
                    bay_home.get("games_observed", window))
                mix_a = bayesian_lambda_blend(
                    bay_away["gf_avg"], bay_away["ga_avg"],
                    away_stats["gf_avg"], away_stats["ga_avg"],
                    bay_away.get("games_observed", window))
            result_bay = _run_bayesian_predict(
                bay_home if model_method == "bayesian" else _with_posterior_means(bay_home, *mix_h),
                bay_away if model_method == "bayesian" else _with_posterior_means(bay_away, *mix_a),
                model["home_advantage"], home_name, away_name)
            oper = result_bay
            response["bayesian"] = {
                "lambdas": result_bay.lambdas,
                "probs": result_bay.probs,
                "top_scores": result_bay.top_scores,
                "proposals": result_bay.proposals,
                "inputs": {"home": bay_home, "away": bay_away},
                "home_bayesian_weight": bay_home.get("bayesian_weight", 0),
                "away_bayesian_weight": bay_away.get("bayesian_weight", 0),
                "model_type": result_bay.model_type,
            }
            response["lambdas"] = result_bay.lambdas
            response["probs"] = result_bay.probs
            response["top_scores"] = result_bay.top_scores
            response["proposals"] = result_bay.proposals
            response["inputs"] = {"home": bay_home, "away": bay_away}
            response["model"]["model_type"] = result_bay.model_type
            response["model"]["method"] = model_method
        else:
            # método poisson: bayesiano apenas como referência (produção intacta)
            result_bay = _run_bayesian_predict(bay_home, bay_away, model["home_advantage"],
                                                home_name, away_name)
            response["bayesian"] = {
                "lambdas": result_bay.lambdas,
                "probs": result_bay.probs,
                "top_scores": result_bay.top_scores,
                "proposals": result_bay.proposals,
                "inputs": {"home": bay_home, "away": bay_away},
                "home_bayesian_weight": bay_home.get("bayesian_weight", 0),
                "away_bayesian_weight": bay_away.get("bayesian_weight", 0),
                "model_type": result_bay.model_type,
            }

    # FASE 14: modificadores contextuais (rest/form/team_ha) sobre o λ operante.
    # Nunca substituem o cálculo Poisson — apenas ajustam λ dentro de bounds (§7).
    flags = _context_flags(model)
    if any(flags.values()):
        kickoff = (match or {}).get("kickoff_datetime") or (match or {}).get("match_date")
        kickoff_ts = _kickoff_ts(kickoff) if kickoff else None
        as_of_ctx = as_of_timestamp or kickoff
        ctx = _apply_context(flags,
                             oper.lambdas["home"], oper.lambdas["away"],
                             league_id, home_team_id, away_team_id,
                             kickoff_ts, as_of_ctx,
                             home_name, away_name,
                             model.get("rho", 0.0))
        if ctx is not None:
            response["lambdas"] = ctx["lambdas"]
            response["probs"] = ctx["probs"]
            response["top_scores"] = ctx["top_scores"]
            response["proposals"] = ctx["proposals"]
            response["context"] = flags
            response["model"]["context"] = flags
            response["data"]["model"]["context"] = flags

    return response
