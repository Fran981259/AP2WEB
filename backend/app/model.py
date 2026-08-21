"""Motor de previsão AP 2.0 — modelo Poisson duplo.

Replica a lógica das abas games/Date/Predictie da planilha AP 2.0,
com as correções recomendadas pela auditoria:
  - λs calculados dinamicamente a partir dos dados importados (não estáticos)
  - probabilidades 1X2 normalizadas a 100% (sum == 1.0)
  - Over/Under, BTTS, placar exato derivados da mesma matriz Poisson
  - Matriz de probabilidades [i][j] = P(casa i gols, fora j gols)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

MAX_GOALS = 10
GOAL_LINES = [1.5, 2.5, 3.5, 4.5]  # linhas padrão de over/under


def poisson_pmf(k: float, lam: float) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * lam**k / math.factorial(int(k))


PoissonPmf = float  # P(X=k) para um valor k, tipo do resultado de poisson_pmf


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
    home: TeamInput = field(default_factory=TeamInput)
    away: TeamInput = field(default_factory=TeamInput)


# Tipagem simplificada para dicionários de probabilidades (usado em retorno de funções)
Probs1x2Types = dict[str, float]  # {"1": float, "X": float, "2": float}
ProbsBttsTypes = dict[str, float]  # {"sim": float, "nao": float}
ProbsOverTypes = dict[float, float]  # {1.5: float, 2.5: float, ...}
ProbsScoresTypes = dict[str, float]  # {"1-0": float, ...}


@dataclass
class PoissonResult:
    lambdas: dict[str, float]
    matrix: list[list[float]]  # prob. placar [i][j] = casa i x fora j
    probs: PoissonProbs  # 1X2, BTTS, Over/Under, placares
    top_scores: list[dict[str, int | float]]
    proposals: list[dict]


def compute_lambdas(home: TeamInput, away: TeamInput, home_advantage: float = 1.0) -> tuple[float, float]:
    """λ casa/fora: média harmônica simples entre ataque próprio e defesa adversária.

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


def build_matrix(lam_home: float, lam_away: float) -> list[list[float]]:
    m = [[0.0] * (MAX_GOALS + 1) for _ in range(MAX_GOALS + 1)]
    for i in range(MAX_GOALS + 1):
        ph = poisson_pmf(i, lam_home)
        for j in range(MAX_GOALS + 1):
            m[i][j] = ph * poisson_pmf(j, lam_away)
    return m


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
    """Regras de propostas baseadas na aba Predictie/Tratamento (AE4-AE19)."""
    out = []
    p1 = probs["1x2"]
    home, away = teams["home"], teams["away"]

    # 1X2
    if p1["X"] < p1["1"] and p1["X"] < p1["2"]:
        out.append({"tipo": "1X2", "jogada": "Lay Empate (Contra o Empate)", "confianca": round(p1["X"] * 100, 1)})
    if p1["1"] >= 0.70:
        out.append({"tipo": "1X2", "jogada": f"Back {home}", "confianca": round(p1["1"] * 100, 1)})
    elif p1["1"] >= 0.60:
        out.append({"tipo": "1X2", "jogada": f"Back {home} (se melhor odd)", "confianca": round(p1["1"] * 100, 1)})
    if p1["2"] >= 0.70:
        out.append({"tipo": "1X2", "jogada": f"Back {away}", "confianca": round(p1["2"] * 100, 1)})
    elif p1["2"] >= 0.60:
        out.append({"tipo": "1X2", "jogada": f"Back {away} (se melhor odd)", "confianca": round(p1["2"] * 100, 1)})

    # Over/Under (usando linha de 1.5 e 2.5)
    ov15 = probs["over"]["over_1.5"]
    ov25 = probs["over"]["over_2.5"]
    un25 = probs["under"]["under_2.5"]
    if ov15 >= 0.82:
        out.append({"tipo": "GOLS", "jogada": "Back Over 0.5/1.5 (entrar cedo)", "confianca": round(ov15 * 100, 1)})
    elif ov15 >= 0.70:
        out.append({"tipo": "GOLS", "jogada": "Back Over 0.5 (entrar aos poucos)", "confianca": round(ov15 * 100, 1)})
    if ov25 >= 0.74:
        out.append({"tipo": "GOLS", "jogada": "Back Over 2.5", "confianca": round(ov25 * 100, 1)})
    elif un25 >= 0.75:
        out.append({"tipo": "GOLS", "jogada": "Back Under 2.5", "confianca": round(un25 * 100, 1)})

    # BTTS
    btts_sim = probs["btts"]["sim"]
    if btts_sim >= 0.55:
        out.append({"tipo": "BTTS", "jogada": "Back BTTS Sim", "confianca": round(btts_sim * 100, 1)})
    elif btts_sim <= 0.45:
        out.append({"tipo": "BTTS", "jogada": "Back BTTS Nao", "confianca": round((1 - btts_sim) * 100, 1)})

    # Placar exato mais provável
    top = top_scores(probs["scores"], 1)
    if top:
        out.append({"tipo": "PLACAR", "jogada": f"Placar exato {top[0]['score']}", "confianca": top[0]["prob"]})

    # Cantos (estimativa simples baseada em lambda total)
    corners_home = lambdas["home"] * 5.2
    corners_away = lambdas["away"] * 5.2
    total_corners = round(corners_home + corners_away, 1)
    out.append({"tipo": "CANTOS", "jogada": f"~{total_corners} cantos no total", "confianca": 0.0, "meta": total_corners})

    return out


def predict(match: MatchInput, home_advantage: float = 1.15) -> PoissonResult:
    lam_home, lam_away = compute_lambdas(match.home, match.away, home_advantage)
    matrix = build_matrix(lam_home, lam_away)
    probs = probabilities(matrix)

    return PoissonResult(
        lambdas={"home": lam_home, "away": lam_away},
        matrix=matrix,
        probs=probs,
        top_scores=top_scores(probs["scores"]),
        proposals=proposals(probs, {"home": match.home.name, "away": match.away.name}, {"home": lam_home, "away": lam_away}),
    )