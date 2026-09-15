"""Serviço de previsão — aplica o motor Poisson (model.py) aos dados do Sofascore.

Alimenta lambdas com as médias de xG (ou gols) marcados/sofridos dos últimos N
jogos de cada time, usando a feature calibrada por liga (learning.get_model).

Integração Bayesian (FASE 13): opcional via USE_BAYESIAN=true
Substitui médias MLE por estimativas Gamma-Poisson posteriors.
"""
from __future__ import annotations

import hashlib
import logging
import os
from types import SimpleNamespace
from datetime import datetime, timezone
from . import db
from .context_features import adjust_lambdas
from .feature_engine import team_match_stats, window_stats
from .learning import get_model
from .model import (
    MatchInput, TeamInput, build_matrix, build_gamma_poisson_matrix, probabilities, top_scores,
    proposals as build_proposals, predict as run_predict,
)
from .bayesian import (
    BayesianEngine,
    build_bayesian_engine_from_history, bayesian_lambda_blend
)

USE_BAYESIAN: bool = os.environ.get("USE_BAYESIAN", "false").lower() == "true"
# Nota P3: global mantido por compatibilidade, mas comportamento determinístico deve usar
# parâmetro explícito `use_bayesian` em _build/predict_* (request-scoped). Ver _should_use_bayesian.

FEATURE_VERSION = "2.0_team_perspective_20260912"
MODEL_CODE_VERSION = "poisson_v4_canonical_dc_20260912"

_log = logging.getLogger("ap2web.prediction")


def _kickoff_ts(kickoff: str | None) -> float | None:
    """Converte kickoff_datetime em timestamp unix (UTC naive)."""
    if not kickoff:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(kickoff.replace("Z", "+0000"), fmt).timestamp()
        except ValueError:
            continue
    try:
        return datetime.strptime(kickoff[:10], "%Y-%m-%d").timestamp()
    except ValueError:
        return None


def _context_flags(model: dict) -> dict:
    # Contextual modifiers are not yet evaluated by the canonical walk-forward
    # backtest. Do not silently activate an unvalidated production path.
    del model
    return {
        "rest": 0,
        "form": 0,
        "team_ha": 0,
    }


def _apply_context(context_flags: dict, lh: float, la: float,
                   league_id: int, home_id: int, away_id: int,
                   kickoff_ts: float | None, as_of: str | None,
                   home_name: str, away_name: str,
                   rho: float) -> dict | None:
    """Aplica modificadores contextuais ao λ e reconstrói probabilidades.

    Retorna None se nenhuma feature estiver habilitada. Sempre veracidade:
    os fatores são limitados e o cálculo Poisson não é substituído (§7).
    """
    if not (context_flags["rest"] or context_flags["form"] or context_flags["team_ha"]):
        return None
    n_h, n_a = adjust_lambdas(
        lh, la, league_id, home_id, away_id,
        match_kickoff_ts=kickoff_ts,
        use_rest=bool(context_flags["rest"]),
        use_form=bool(context_flags["form"]),
        use_team_ha=bool(context_flags["team_ha"]),
        as_of=as_of,
    )
    if (n_h, n_a) == (lh, la):
        return None
    matrix = build_matrix(n_h, n_a, rho)
    probs = probabilities(matrix)
    return {
        "lambdas": {"home": n_h, "away": n_a},
        "probs": probs,
        "top_scores": top_scores(probs["scores"]),
        "proposals": build_proposals(probs, {"home": home_name, "away": away_name},
                                     {"home": n_h, "away": n_a}),
    }


def _played_rows(cols: str, extra_where: str, params: list,
                 limit: int, as_of_timestamp: str | None = None) -> list:
    """Fonte ÚNICA para busca de jogos jogados de uma liga (auditoria/temporal).

    Aplica consistentemente o filtro as-of (`date(kickoff) < date(?)`) quando
    fornecido, prevenindo data leakage em todas as consultas de previsão.
    `params` deve conter os valores de `extra_where` na ordem (league_id primeiro).
    """
    query = (
        f"SELECT {cols} "
        "FROM matches m "
        "JOIN teams th ON th.id=m.home_team_id "
        "JOIN teams ta ON ta.id=m.away_team_id "
        "WHERE m.league_id=? AND m.status='played' AND m.score_home IS NOT NULL "
        "AND m.score_away IS NOT NULL "
        f"{extra_where} "
    )
    all_params = list(params)
    if as_of_timestamp:
        query += "AND datetime(m.kickoff_datetime) < datetime(?) "
        all_params.append(as_of_timestamp)
    query += "ORDER BY m.kickoff_datetime DESC LIMIT ?"
    all_params.append(limit)
    return db.run_query(query, tuple(all_params))


def _avg_stats(league_id: int, team_id: int, window: int, feature: str,
               as_of_timestamp: str | None = None) -> dict:
    """Computa médias de gols usando Feature Engine unificado.

    Se as_of_timestamp for fornecido, somente jogos com kickoff_datetime anterior
    são considerados (prevenção de data leakage temporal).
    """
    rows = _played_rows(
        "m.kickoff_datetime, m.home_team_id, m.away_team_id, "
        "m.score_home, m.score_away, m.xg_home, m.xg_away",
        "AND (m.home_team_id=? OR m.away_team_id=?)",
        [league_id, team_id, team_id], window, as_of_timestamp)
    return window_stats([dict(r) for r in rows], team_id, window, feature)


_BAYESIAN_ENGINES: dict[int, BayesianEngine] = {}
_BAYESIAN_ENGINES_SNAPSHOT: dict[int, str] = {}  # league_id -> snapshot iso for cache key

def invalidate_prediction_cache(league_id: int | None = None):
    """Cache invalidation after sync/calibration/promotion (P5)."""
    if league_id is None:
        _BAYESIAN_ENGINES.clear()
        _BAYESIAN_ENGINES_SNAPSHOT.clear()
        try:
            from .feature_engine import _cached_team_stats
            _cached_team_stats.cache_clear()
        except Exception:
            pass
        _log.info("cache invalidated all")
    else:
        _BAYESIAN_ENGINES.pop(league_id, None)
        _BAYESIAN_ENGINES_SNAPSHOT.pop(league_id, None)
        try:
            from .feature_engine import _cached_team_stats
            _cached_team_stats.cache_clear()
        except Exception:
            pass
        _log.debug("cache invalidated league=%s", league_id)

def _get_bayesian_engine(league_id: int) -> BayesianEngine:
    if league_id not in _BAYESIAN_ENGINES:
        matches = [dict(r) for r in db.run_query(
            "SELECT m.kickoff_datetime, m.home_team_id, m.away_team_id, "
            "       m.score_home, m.score_away, th.name AS home_name, ta.name AS away_name "
            "FROM matches m "
            "JOIN teams th ON th.id=m.home_team_id "
            "JOIN teams ta ON ta.id=m.away_team_id "
            "WHERE m.league_id=? AND m.status='played' AND m.score_home IS NOT NULL AND m.score_away IS NOT NULL "
            "ORDER BY m.kickoff_datetime",
            (league_id,)
        )]
        _BAYESIAN_ENGINES[league_id] = build_bayesian_engine_from_history(matches)
    return _BAYESIAN_ENGINES[league_id]


def _avg_stats_bayesian(league_id: int, team_id: int, window: int, feature: str,
                        as_of_timestamp: str | None = None) -> dict:
    """Posterior Gamma ACUMULADO sobre TODAS as partidas anteriores a `as_of`.

    O posterior cresce com todo o histórico já visto — não é limitado à janela.
    Corrigido na auditoria: o engine é criado do zero com o prior e atualizado
    apenas com as partidas anteriores a `as_of` (filtro temporal), eliminando
    (1) a dupla contagem dos jogos recentes e (2) o vazamento de jogos futuros
    que existia ao pré-carregar o engine com a liga inteira.

    Posterior = Gamma(α0 + Σ gols, β0 + n). `games_observed` alimenta o peso
    de credibilidade do método híbrido.
    """
    query = (
        "SELECT m.kickoff_datetime, m.home_team_id, m.away_team_id, "
        "m.score_home, m.score_away, m.xg_home, m.xg_away "
        "FROM matches m "
        "WHERE m.league_id=? AND (m.home_team_id=? OR m.away_team_id=?) "
        "  AND m.status='played' AND m.score_home IS NOT NULL AND m.score_away IS NOT NULL "
    )
    params = [league_id, team_id, team_id]
    if as_of_timestamp:
        query += " AND datetime(m.kickoff_datetime) < datetime(?) "
        params.append(as_of_timestamp)
    query += " ORDER BY m.kickoff_datetime, m.id"
    rows = db.run_query(query, tuple(params))
    n = len(rows)
    if not rows:
        return {"gf_avg": 1.3 / 5.0, "ga_avg": 1.3 / 5.0,
                "gf_alpha": 1.3, "gf_beta": 5.0, "ga_alpha": 1.3, "ga_beta": 5.0,
                "bayesian_weight": 0.0, "games_observed": 0}

    engine = BayesianEngine()
    for r in rows:
        r = dict(r)
        selected = team_match_stats(r, team_id, feature)
        gf, ga = selected["gf"], selected["ga"]
        engine.update_team(team_id, f"Team {team_id}", gf=gf, ga=ga)

    state = engine.teams.get(team_id)
    if state:
        weight = min(n / 10.0, 1.0)
        return {
            "gf_avg": state.lambda_gf,
            "ga_avg": state.lambda_ga,
            "gf_alpha": state.alpha_gf,
            "gf_beta": state.beta_gf,
            "ga_alpha": state.alpha_ga,
            "ga_beta": state.beta_ga,
            "bayesian_weight": weight,
            "games_observed": n,
        }
    return {"gf_avg": 1.3 / 5.0, "ga_avg": 1.3 / 5.0,
            "gf_alpha": 1.3, "gf_beta": 5.0, "ga_alpha": 1.3, "ga_beta": 5.0,
            "bayesian_weight": 0.0, "games_observed": 0}


def _match_gamma(home: dict, away: dict, home_advantage: float) -> tuple[float, float, float, float]:
    """Moment-match attack and opposing-defense Gamma posteriors for a match."""
    def combine(alpha_a, beta_a, alpha_b, beta_b):
        mean = (alpha_a / beta_a + alpha_b / beta_b) / 2
        variance = (alpha_a / beta_a ** 2 + alpha_b / beta_b ** 2) / 4
        return mean ** 2 / variance, mean / variance

    ha, hb = combine(home["gf_alpha"], home["gf_beta"], away["ga_alpha"], away["ga_beta"])
    aa, ab = combine(away["gf_alpha"], away["gf_beta"], home["ga_alpha"], home["ga_beta"])
    # Scaling a Gamma rate by c keeps alpha and changes beta to beta/c.
    return ha, hb / home_advantage, aa, ab


def _run_bayesian_predict(home: dict, away: dict, home_advantage: float,
                          home_name: str, away_name: str):
    ha, hb, aa, ab = _match_gamma(home, away, home_advantage)
    matrix = build_gamma_poisson_matrix(ha, hb, aa, ab)
    probs = probabilities(matrix)
    lambdas = {"home": round(ha / hb, 4), "away": round(aa / ab, 4)}
    return SimpleNamespace(lambdas=lambdas, probs=probs,
                           top_scores=top_scores(probs["scores"]),
                           proposals=build_proposals(probs, {"home": home_name, "away": away_name}, lambdas),
                           model_type="gamma_poisson")


def _with_posterior_means(stats: dict, gf_mean: float, ga_mean: float) -> dict:
    """Retain posterior uncertainty while applying an explicit hybrid mean."""
    out = dict(stats)
    for prefix, mean in (("gf", gf_mean), ("ga", ga_mean)):
        variance = stats[f"{prefix}_alpha"] / stats[f"{prefix}_beta"] ** 2
        out[f"{prefix}_alpha"] = mean ** 2 / variance
        out[f"{prefix}_beta"] = mean / variance
    return out


def _avg_stats_detail(league_id: int, team_id: int, window: int, feature: str,
                      as_of_timestamp: str | None = None) -> dict:
    """Jogos brutos que alimentaram as médias (auditoria do confronto)."""
    rows = _played_rows(
        "m.kickoff_datetime, th.name AS home, ta.name AS away, "
        "m.score_home, m.score_away, m.xg_home, m.xg_away, m.home_team_id, m.away_team_id",
        "AND (m.home_team_id=? OR m.away_team_id=?)",
        [league_id, team_id, team_id], window, as_of_timestamp)
    games = []
    for m in rows:
        row_dict = dict(m)
        home_side = row_dict["home_team_id"] == team_id
        selected = team_match_stats(row_dict, team_id, feature)
        gf, ga = selected["gf"], selected["ga"]
        games.append({
            "date": m["kickoff_datetime"][:10] if m["kickoff_datetime"] else None,
            "opponent": m["away"] if home_side else m["home"],
            "side": "casa" if home_side else "fora",
            "gf": gf,
            "ga": ga,
            "xg": m["xg_home"] if home_side else m["xg_away"],
            "xg_against": m["xg_away"] if home_side else m["xg_home"],
        })
    return {"games_used": games, "count": len(games)}


def _model_for(league_id: int) -> dict:
    return get_model(league_id)


def _recent_form(league_id: int, team_id: int, limit: int = 5,
                 as_of_timestamp: str | None = None) -> list[dict]:
    rows = _played_rows(
        "m.kickoff_datetime, m.score_home, m.score_away, m.status, "
        "m.home_team_id, m.away_team_id, th.name AS home, ta.name AS away",
        "AND (m.home_team_id=? OR m.away_team_id=?)",
        [league_id, team_id, team_id], limit, as_of_timestamp)
    out = []
    for r in rows:
        played_home = r["home_team_id"] == team_id
        gf = r["score_home"] if played_home else r["score_away"]
        ga = r["score_away"] if played_home else r["score_home"]
        out.append({
            "date": r["kickoff_datetime"][:10] if r["kickoff_datetime"] else None,
            "opponent": r["away"] if played_home else r["home"],
            "played_home": played_home,
            "gf": gf,
            "ga": ga,
            "result": "W" if gf > ga else ("D" if gf == ga else "L"),
        })
    return out


def _h2h(league_id: int, home_team_id: int, away_team_id: int, limit: int = 5,
         as_of_timestamp: str | None = None) -> list[dict]:
    rows = _played_rows(
        "m.kickoff_datetime, m.score_home, m.score_away, m.xg_home, m.xg_away, "
        "th.name AS home, ta.name AS away",
        "AND ((m.home_team_id=? AND m.away_team_id=?) "
        "OR (m.home_team_id=? AND m.away_team_id=?))",
        [league_id, home_team_id, away_team_id, away_team_id, home_team_id],
        limit, as_of_timestamp)
    return [dict(r) for r in rows]


def _team_card(league_id: int, team_id: int, name: str, stats: dict, feature: str,
               as_of_timestamp: str | None = None) -> dict:
    query = (
        "SELECT COUNT(*) c FROM matches "
        "WHERE league_id=? AND (home_team_id=? OR away_team_id=?) "
        "  AND status='played' AND score_home IS NOT NULL "
    )
    params = [league_id, team_id, team_id]
    if as_of_timestamp:
        query += " AND datetime(kickoff_datetime) < datetime(?)"
        params.append(as_of_timestamp)
    gp = db.run_query(query, tuple(params))[0]["c"] or 0
    return {
        "name": name,
        "gf_avg": stats.get("gf_avg", 0),
        "ga_avg": stats.get("ga_avg", 0),
        "feature": feature,
        "games": gp,
        "form": _recent_form(league_id, team_id, as_of_timestamp=as_of_timestamp),
    }


def _compare(league_id: int, home_id: int, away_id: int,
             home_name: str, away_name: str, home_stats: dict, away_stats: dict,
             feature: str, as_of_timestamp: str | None = None) -> dict:
    return {
        "home": _team_card(league_id, home_id, home_name, home_stats, feature, as_of_timestamp),
        "away": _team_card(league_id, away_id, away_name, away_stats, feature, as_of_timestamp),
        "h2h": _h2h(league_id, home_id, away_id, as_of_timestamp=as_of_timestamp),
    }


def _should_use_bayesian(model_method: str, use_bayesian: bool | None) -> bool:
    """Determinístico por request: se use_bayesian explícito, usa-o; senão cai no método da liga + flag global."""
    if use_bayesian is not None:
        return bool(use_bayesian)
    if model_method in ("bayesian", "hybrid"):
        return True
    return bool(USE_BAYESIAN)

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


def predict_match(match_id: int, as_of_timestamp: str | None = None, use_bayesian: bool | None = None) -> dict:
    # O jogo previsto deve sempre ser encontrado; o filtro as-of aplica-se
    # apenas ao histórico usado nas features (dentro de _build).
    query = (
        "SELECT m.*, l.name AS league_name, th.name AS home_name, ta.name AS away_name "
        "FROM matches m "
        "JOIN leagues l ON l.id=m.league_id "
        "JOIN teams th ON th.id=m.home_team_id "
        "JOIN teams ta ON ta.id=m.away_team_id "
        "WHERE m.id=?"
    )
    rows = db.run_query(query, (match_id,))
    if not rows:
        raise IndexError("Partida não encontrada")
    m = rows[0]
    kickoff = m["kickoff_datetime"]
    cutoff = as_of_timestamp or kickoff
    if as_of_timestamp and kickoff:
        try:
            if datetime.fromisoformat(as_of_timestamp.replace("Z", "+00:00")) > datetime.fromisoformat(kickoff.replace("Z", "+00:00")):
                raise ValueError("as_of_timestamp cannot be after the match kickoff")
        except ValueError as exc:
            if str(exc).startswith("as_of_timestamp"):
                raise
            raise ValueError("as_of_timestamp must be ISO-8601") from exc
    return _build(m["league_id"], m["home_team_id"], m["away_team_id"],
                  m["home_name"], m["away_name"], m["league_name"], m, cutoff, use_bayesian)


def predict_league_upcoming(league_id: int, limit: int = 10,
                             as_of_timestamp: str | None = None, use_bayesian: bool | None = None) -> list[dict]:
    condition = "AND status='scheduled' AND datetime(kickoff_datetime) >= datetime(?)"
    params = (league_id, as_of_timestamp or datetime.now(timezone.utc).isoformat(), limit)
    query = (
        "SELECT id FROM matches WHERE league_id=? {condition} "
        "ORDER BY kickoff_datetime, id LIMIT ?"
    ).format(condition=condition)
    rows = db.run_query(query, params)
    return [predict_match(r["id"], as_of_timestamp, use_bayesian) for r in rows]


def predict_fixture(league_id: int, home_team_id: int, away_team_id: int,
                    as_of_timestamp: str | None = None, use_bayesian: bool | None = None) -> dict:
    l = db.run_query("SELECT id, name, country FROM leagues WHERE id=?", (league_id,))[0]
    rows = db.run_query(
        "SELECT id, name FROM teams WHERE league_id=? AND id IN (?,?)",
        (league_id, home_team_id, away_team_id))
    names = {r["id"]: r["name"] for r in rows}
    if not names or home_team_id not in names or away_team_id not in names:
        raise IndexError("Confronto não encontrado")
    return _build(league_id, home_team_id, away_team_id,
                  names[home_team_id], names[away_team_id], l["name"],
                  as_of_timestamp=as_of_timestamp, use_bayesian=use_bayesian)
