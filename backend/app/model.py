"""Motor de previsão AP 3.0 — Poisson + Dixon-Coles + Bayesian Updating.

Evolução do AP 2.0 com correções matemáticas rigorosas:
  - Dixon-Coles (1997): fator τ de dependência para placares baixos (0-0, 1-0, 0-1, 1-1)
  - Bayesian updating: priors Gamma → posteriores com observações de gols
  - λs via médias aritméticas de ataque/defesa por time (não regressão ajustada)
  - Matriz de probabilidades [i][j] = P(casa i gols, fora j gols) corrigida

Referências:
  Dixon & Coles (1997) "Modelling Association Football Scores"
  Maher (1982) "Modelling Association Football Scores"
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

MAX_GOALS = 10
GOAL_LINES = [1.5, 2.5, 3.5, 4.5]  # linhas padrão de over/under


def poisson_pmf(k: float, lam: float) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * lam**k / math.factorial(int(k))


def gamma_poisson_pmf(k: int, alpha: float, beta: float) -> float:
    """Posterior predictive for Poisson observations with Gamma(alpha, beta) rate."""
    if alpha <= 0 or beta <= 0:
        raise ValueError("Gamma parameters must be positive")
    return math.exp(math.lgamma(k + alpha) - math.lgamma(alpha) - math.lgamma(k + 1)
                    + alpha * math.log(beta / (beta + 1)) + k * math.log(1 / (beta + 1)))


@dataclass
class TeamInput:
    name: str
    # médias de gols/xG (da importação / histórico)
    gf_avg: float = 0.0  # média de gols marcados (ou xG marcado)
    ga_avg: float = 0.0  # média de gols sofridos (ou xG sofridos)
    # registros recentes opcionais (para form e propostas)
    matches: list[dict] = field(default_factory=list)


@dataclass
class MatchInput:
    league: str = ""
    home: TeamInput = field(default_factory=lambda: TeamInput(name=""))
    away: TeamInput = field(default_factory=lambda: TeamInput(name=""))


@dataclass
class PoissonResult:
    lambdas: dict[str, float]
    matrix: list[list[float]]  # prob. placar [i][j] = casa i x fora j
    probs: dict  # 1X2, BTTS, Over/Under, placares
    top_scores: list[dict[str, int | float]]
    proposals: list[dict]
    rho: float = 0.0  # parâmetro Dixon-Coles (0 = Poisson puro)
    model_type: str = "poisson"  # "poisson" ou "dixon_coles"


def compute_lambdas(home: TeamInput, away: TeamInput, home_advantage: float = 1.0) -> tuple[float, float]:
    """λ casa/fora: média aritmética entre ataque próprio e defesa adversária.

    λcasa = média(atk_casa, def_fora) * fator_mando
    λfora = média(atk_fora, def_casa)
    Se faltar dado de uma das pontas, usa a outra; se faltar tudo, usa 1.2 (neutro).
    """
    def avg(*xs: float) -> float:
        xs = [x for x in xs if x > 0]
        return sum(xs) / len(xs) if xs else 0.0

    atk_home = home.gf_avg
    def_away = away.ga_avg
    atk_away = away.gf_avg
    def_home = home.ga_avg

    lam_home = avg(atk_home, def_away) * home_advantage
    lam_away = avg(atk_away, def_home)

    # fallback neutro se nenhum dado disponível
    if lam_home <= 0 and lam_away <= 0:
        lam_home, lam_away = 1.2, 1.2
    elif lam_home <= 0:
        lam_home = lam_away
    elif lam_away <= 0:
        lam_away = lam_home

    return round(lam_home, 4), round(lam_away, 4)


def dixon_coles_tau(i: int, j: int, lam_home: float, lam_away: float,
                    rho: float) -> float:
    """Canonical Dixon–Coles low-score factors (home i, away j)."""
    if i == 0 and j == 0:
        return 1.0 - lam_home * lam_away * rho
    elif i == 1 and j == 0:
        return 1.0 + lam_away * rho
    elif i == 0 and j == 1:
        return 1.0 + lam_home * rho
    elif i == 1 and j == 1:
        return 1.0 - rho
    return 1.0


def build_matrix(lam_home: float, lam_away: float,
                 rho: float = 0.0) -> list[list[float]]:
    """Constrói matriz de probabilidades Poisson com correção Dixon-Coles.

    Para ρ=0, resultado idêntico ao Poisson puro.
    Para ρ≠0, os 4 placares baixos (0-0, 1-0, 0-1, 1-1) são ajustados
    pelo fator τ, e a matriz é renormalizada.
    """
    if not all(math.isfinite(v) for v in (lam_home, lam_away, rho)) or min(lam_home, lam_away) < 0:
        raise ValueError("Lambdas must be finite and non-negative; rho must be finite")
    # Project rho to its match-specific admissible interval so every tau >= 0.
    # This is an explicit numerical policy, not a fitted Dixon–Coles regression.
    lower = max((-1 / v for v in (lam_home, lam_away) if v > 0), default=-0.5)
    upper = min(1.0, 1 / (lam_home * lam_away)) if lam_home * lam_away > 0 else 1.0
    rho = max(lower, min(upper, rho))
    m = [[0.0] * (MAX_GOALS + 1) for _ in range(MAX_GOALS + 1)]
    total = 0.0

    for i in range(MAX_GOALS + 1):
        ph = poisson_pmf(i, lam_home)
        for j in range(MAX_GOALS + 1):
            p = ph * poisson_pmf(j, lam_away)
            # Aplicar Dixon-Coles τ para os 4 placares baixos
            tau = dixon_coles_tau(i, j, lam_home, lam_away, rho)
            m[i][j] = p * tau
            total += m[i][j]

    # Renormalizar para garantir soma = 1.0 (corrige drift de ponto flutuante)
    if total > 0:
        inv_total = 1.0 / total
        for i in range(MAX_GOALS + 1):
            for j in range(MAX_GOALS + 1):
                m[i][j] *= inv_total

    return m


def build_gamma_poisson_matrix(home_alpha: float, home_beta: float,
                               away_alpha: float, away_beta: float) -> list[list[float]]:
    """Independent Gamma-Poisson posterior predictive score matrix.

    Dixon-Coles is intentionally not applied here: its correction is calibrated
    for Poisson lambdas and cannot be silently reused for a negative binomial.
    """
    home = [gamma_poisson_pmf(i, home_alpha, home_beta) for i in range(MAX_GOALS + 1)]
    away = [gamma_poisson_pmf(i, away_alpha, away_beta) for i in range(MAX_GOALS + 1)]
    total = sum(home) * sum(away)
    return [[home[i] * away[j] / total for j in range(MAX_GOALS + 1)]
            for i in range(MAX_GOALS + 1)]


def _normalize(d: dict[str, float]) -> dict[str, float]:
    total = sum(d.values())
    if total <= 0:
        return {k: 0.0 for k in d}
    return {k: v / total for k, v in d.items()}


def probabilities(matrix: list[list[float]]) -> dict:
    n = len(matrix)
    home_w = draw = away_w = 0.0
    btts = 0.0
    over = {1.5: 0.0, 2.5: 0.0, 3.5: 0.0, 4.5: 0.0}
    score_prob: dict[str, float] = {}

    for i in range(n):
        for j in range(n):
            p = matrix[i][j]
            if i > j:
                home_w += p
            elif i == j:
                draw += p
            else:
                away_w += p
            if i >= 1 and j >= 1:
                btts += p
            tg = i + j
            for line in over:
                if tg > line:
                    over[line] += p
            score_prob[f"{i}-{j}"] = p

    p1x2 = _normalize({"1": home_w, "X": draw, "2": away_w})
    p_btts = {"sim": btts, "nao": 1.0 - btts}
    p_over = {f"over_{line}": over[line] for line in over}
    p_under = {f"under_{line}": 1.0 - over[line] for line in over}

    return {
        "1x2": p1x2,
        "odds_1x2": {k: round(1.0 / v, 2) if v > 0 else 999.0 for k, v in p1x2.items()},
        "btts": p_btts,
        "over": p_over,
        "under": p_under,
        "scores": score_prob,
    }


def top_scores(score_prob: dict[str, float], k: int = 10) -> list[dict]:
    ranked = sorted(score_prob.items(), key=lambda x: -x[1])
    out = []
    for score, p in ranked[:k]:
        out.append({"score": score, "prob": round(p * 100, 2), "odd": round(1.0 / p, 2) if p > 0 else 999})
    return out


def proposals(probs: dict, teams: dict, lambdas: dict) -> list[dict]:
    """Regras de propostas — só gera quando confiança >= 55%."""
    out = []
    p1 = probs["1x2"]
    home, away = teams["home"], teams["away"]

    # 1X2 — só propõe quando favorito tem >= 55%
    if p1["1"] >= 0.55:
        out.append({"tipo": "1X2", "jogada": f"Back {home}", "confianca": round(p1["1"] * 100, 1)})
    elif p1["2"] >= 0.55:
        out.append({"tipo": "1X2", "jogada": f"Back {away}", "confianca": round(p1["2"] * 100, 1)})
    # Lay empate só se empate for claramente o mais provável
    if p1["X"] >= 0.35 and p1["X"] > p1["1"] and p1["X"] > p1["2"]:
        out.append({"tipo": "1X2", "jogada": "Lay Empate (Contra o Empate)", "confianca": round((1 - p1["X"]) * 100, 1)})

    # Over/Under — thresholds realistas
    ov15 = probs["over"]["over_1.5"]
    ov25 = probs["over"]["over_2.5"]
    un25 = probs["under"]["under_2.5"]
    if ov25 >= 0.65:
        out.append({"tipo": "GOLS", "jogada": "Back Over 2.5", "confianca": round(ov25 * 100, 1)})
    elif un25 >= 0.65:
        out.append({"tipo": "GOLS", "jogada": "Back Under 2.5", "confianca": round(un25 * 100, 1)})
    if ov15 >= 0.75:
        out.append({"tipo": "GOLS", "jogada": "Back Over 1.5", "confianca": round(ov15 * 100, 1)})

    # BTTS — usa probabilidade real do modelo Poisson
    btts_sim = probs["btts"]["sim"]
    if btts_sim >= 0.58:
        out.append({"tipo": "BTTS", "jogada": "Back BTTS Sim", "confianca": round(btts_sim * 100, 1)})
    elif btts_sim <= 0.42:
        out.append({"tipo": "BTTS", "jogada": "Back BTTS Nao", "confianca": round((1 - btts_sim) * 100, 1)})

    # Placar exato — só o mais provável se tiver >= 8%
    top = top_scores(probs["scores"], 1)
    if top and top[0]["prob"] >= 8:
        out.append({"tipo": "PLACAR", "jogada": f"Placar exato {top[0]['score']}", "confianca": top[0]["prob"]})

    return out


def predict(match: MatchInput, home_advantage: float = 1.15,
            rho: float = 0.0) -> PoissonResult:
    """Previsão Poisson com Dixon-Coles.

    Args:
        match: dados do confronto (home/away team inputs)
        home_advantage: fator de mando calibrado (default 1.15)
        rho: parâmetro de dependência Dixon-Coles (0 = Poisson puro)
             Tipicamente ≈ -0.13 para futebol.

    Returns:
        PoissonResult com lambdas, matrix, probs, top_scores, proposals
    """
    lam_home, lam_away = compute_lambdas(match.home, match.away, home_advantage)
    matrix = build_matrix(lam_home, lam_away, rho)
    probs = probabilities(matrix)

    model_type = "dixon_coles" if rho != 0.0 else "poisson"

    return PoissonResult(
        lambdas={"home": lam_home, "away": lam_away},
        matrix=matrix,
        probs=probs,
        top_scores=top_scores(probs["scores"]),
        proposals=proposals(probs, {"home": match.home.name, "away": match.away.name},
                            {"home": lam_home, "away": lam_away}),
        rho=rho,
        model_type=model_type,
    )
