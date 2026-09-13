"""Bayesian Engine — Gamma-Poisson Conjugate Priors para força de ataque/defesa.

Teoria:
  - Prior: Gamma(α, β) onde λ ~ Gamma(α, β) representa força do time
  - Likelihood: Poisson(gols | λ)
  - Posterior: Gamma(α + gols, β + 1) [conjugate update]
  - Predição: P(gols) = Poisson(gols | λ_posterior) com E[λ] = α/β

Vantagem sobre MLE (média simples):
  - Times com poucos jogos: prior domina (regressão à média)
  - Times com muitos jogos: dados dominam (comportamento real)
  - Intervalos de credibilidade 95% para λ

Referência: Kruschke, J. "Doing Bayesian Data Analysis" (2015) Cap. 5.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


PRIOR_ALPHA: float = 1.3
PRIOR_BETA: float = 5.0


@dataclass
class TeamBayesianState:
    team_id: int
    team_name: str
    alpha_gf: float
    beta_gf: float
    alpha_ga: float
    beta_ga: float
    games_observed: int = 0

    @property
    def lambda_gf(self) -> float:
        return self.alpha_gf / self.beta_gf

    @property
    def lambda_ga(self) -> float:
        return self.alpha_ga / self.beta_ga

    @property
    def std_gf(self) -> float:
        return math.sqrt(self.alpha_gf) / self.beta_gf

    @property
    def std_ga(self) -> float:
        return math.sqrt(self.alpha_ga) / self.beta_ga

    def credible_interval_gf(self, confidence: float = 0.95) -> tuple[float, float]:
        from scipy.stats import gamma as gamma_dist
        lower = gamma_dist.ppf((1 - confidence) / 2, self.alpha_gf, scale=1 / self.beta_gf)
        upper = gamma_dist.ppf((1 + confidence) / 2, self.alpha_gf, scale=1 / self.beta_gf)
        return (round(lower, 3), round(upper, 3))

    def credible_interval_ga(self, confidence: float = 0.95) -> tuple[float, float]:
        from scipy.stats import gamma as gamma_dist
        lower = gamma_dist.ppf((1 - confidence) / 2, self.alpha_ga, scale=1 / self.beta_ga)
        upper = gamma_dist.ppf((1 + confidence) / 2, self.alpha_ga, scale=1 / self.beta_ga)
        return (round(lower, 3), round(upper, 3))

    def update(self, gf: float, ga: float) -> None:
        self.alpha_gf += gf
        self.beta_gf += 1.0
        self.alpha_ga += ga
        self.beta_ga += 1.0
        self.games_observed += 1

    def to_dict(self) -> dict:
        return {
            "team_id": self.team_id,
            "team_name": self.team_name,
            "lambda_gf": round(self.lambda_gf, 3),
            "lambda_ga": round(self.lambda_ga, 3),
            "std_gf": round(self.std_gf, 3),
            "std_ga": round(self.std_ga, 3),
            "ci_gf_95": self.credible_interval_gf(),
            "ci_ga_95": self.credible_interval_ga(),
            "games_observed": self.games_observed,
            "credibility_weight": min(self.games_observed / 10.0, 1.0),
        }


class BayesianEngine:
    def __init__(self, prior_alpha: float = PRIOR_ALPHA, prior_beta: float = PRIOR_BETA):
        self.prior_alpha = prior_alpha
        self.prior_beta = prior_beta
        self.teams: dict[int, TeamBayesianState] = {}

    def get_or_create_team(self, team_id: int, team_name: str) -> TeamBayesianState:
        if team_id not in self.teams:
            self.teams[team_id] = TeamBayesianState(
                team_id=team_id,
                team_name=team_name,
                alpha_gf=self.prior_alpha,
                beta_gf=self.prior_beta,
                alpha_ga=self.prior_alpha,
                beta_ga=self.prior_beta,
            )
        return self.teams[team_id]

    def update_team(self, team_id: int, team_name: str, gf: float, ga: float) -> None:
        state = self.get_or_create_team(team_id, team_name)
        state.update(gf, ga)

    def get_lambda(self, team_id: int) -> tuple[float, float]:
        if team_id in self.teams:
            t = self.teams[team_id]
            return (round(t.lambda_gf, 3), round(t.lambda_ga, 3))
        return (self.prior_alpha / self.prior_beta, self.prior_alpha / self.prior_beta)

    def get_state(self, team_id: int) -> Optional[dict]:
        if team_id in self.teams:
            return self.teams[team_id].to_dict()
        return None

    def summary(self) -> dict:
        return {
            "prior_alpha": self.prior_alpha,
            "prior_beta": self.prior_beta,
            "prior_mean": round(self.prior_alpha / self.prior_beta, 3),
            "teams_observed": len(self.teams),
            "teams": {
                tid: state.to_dict()
                for tid, state in self.teams.items()
            }
        }


def build_bayesian_engine_from_history(
    matches: list[dict],
    prior_alpha: float = PRIOR_ALPHA,
    prior_beta: float = PRIOR_BETA,
) -> BayesianEngine:
    engine = BayesianEngine(prior_alpha=prior_alpha, prior_beta=prior_beta)

    for match in matches:
        if not match.get("kickoff_datetime"):
            continue
        match = dict(match)
        home_id = match.get("home_team_id")
        away_id = match.get("away_team_id")
        home_name = match.get("home_name", f"Team {home_id}")
        away_name = match.get("away_name", f"Team {away_id}")
        gf = float(match.get("score_home", 0) or 0)
        ga = float(match.get("score_away", 0) or 0)

        if home_id and away_id:
            engine.update_team(home_id, home_name, gf=gf, ga=ga)
            engine.update_team(away_id, away_name, gf=ga, ga=gf)

    return engine


def bayesian_lambda_blend(
    bayesian_gf: float,
    bayesian_ga: float,
    mle_gf: float,
    mle_ga: float,
    games_observed: int,
    blend_prior: int = 10,
) -> tuple[float, float]:
    weight = min(games_observed / blend_prior, 1.0)
    blended_gf = weight * bayesian_gf + (1 - weight) * mle_gf
    blended_ga = weight * bayesian_ga + (1 - weight) * mle_ga
    return (round(blended_gf, 3), round(blended_ga, 3))


if __name__ == "__main__":
    from . import db

    matches = db.run_query(
        "SELECT m.id, m.kickoff_datetime, m.home_team_id, m.away_team_id, "
        "       m.score_home, m.score_away, th.name AS home_name, ta.name AS away_name "
        "FROM matches m "
        "JOIN teams th ON th.id=m.home_team_id "
        "JOIN teams ta ON ta.id=m.away_team_id "
        "WHERE m.league_id=? AND m.status='played' "
        "ORDER BY m.kickoff_datetime "
        "LIMIT 100",
        (17,)
    )

    engine = build_bayesian_engine_from_history(matches)
    summary = engine.summary()
    print(f"Bayesian Engine inicializado: {summary['teams_observed']} times")
    print(f"Prior médio: {summary['prior_mean']}")

    for team_id, state in list(engine.teams.items())[:3]:
        s = engine.get_state(team_id)
        print(f"\n{s['team_name']}:")
        print(f"  λ_gf: {s['lambda_gf']} (CI 95%: {s['ci_gf_95']})")
        print(f"  λ_ga: {s['lambda_ga']} (CI 95%: {s['ci_ga_95']})")
        print(f"  Jogos observados: {s['games_observed']}")
        print(f"  Peso de credibilidade: {s['credibility_weight']:.2%}")
