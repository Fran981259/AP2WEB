"""Bayesian path: engine cache, posteriors, gamma match and method switch."""
from __future__ import annotations

from types import SimpleNamespace

from .. import db
from ..bayesian import (
    BayesianEngine,
    build_bayesian_engine_from_history,
)
from ..feature_engine import team_match_stats
from ..model import (
    build_gamma_poisson_matrix,
    probabilities,
    proposals as build_proposals,
    top_scores,
)
from .settings import USE_BAYESIAN, _log


_BAYESIAN_ENGINES: dict[int, BayesianEngine] = {}
_BAYESIAN_ENGINES_SNAPSHOT: dict[int, str] = {}  # league_id -> snapshot iso for cache key
def invalidate_prediction_cache(league_id: int | None = None):
    """Cache invalidation after sync/calibration/promotion (P5)."""
    if league_id is None:
        _BAYESIAN_ENGINES.clear()
        _BAYESIAN_ENGINES_SNAPSHOT.clear()
        try:
            from ..feature_engine import _cached_team_stats
            _cached_team_stats.cache_clear()
        except Exception:
            pass
        _log.info("cache invalidated all")
    else:
        _BAYESIAN_ENGINES.pop(league_id, None)
        _BAYESIAN_ENGINES_SNAPSHOT.pop(league_id, None)
        try:
            from ..feature_engine import _cached_team_stats
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
def _should_use_bayesian(model_method: str, use_bayesian: bool | None) -> bool:
    """Determinístico por request: se use_bayesian explícito, usa-o; senão cai no método da liga + flag global."""
    if use_bayesian is not None:
        return bool(use_bayesian)
    if model_method in ("bayesian", "hybrid"):
        return True
    return bool(USE_BAYESIAN)
