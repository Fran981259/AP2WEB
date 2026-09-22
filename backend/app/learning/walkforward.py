"""Honest walk-forward backtest engine (no leakage)."""
from __future__ import annotations

import math
from collections import deque

from .. import db
from ..feature_engine import compute_match_stats, compute_team_stats
from ..model import MatchInput, TeamInput, predict as run_predict
from .grids import MIN_SAMPLES


def _team_lambdas(history: deque, window: int, feature: str) -> dict:
    """λ (médio) do tempo usando os últimos `window` jogos da janela.

    Agora delega ao Feature Engine para garantir consistência com prediction.py.
    """
    return compute_team_stats(history, window, feature)


def _predict_probs(home_lambdas: dict, away_lambdas: dict,
                   home_adv: float, rho: float = 0.0) -> dict:
    """Previsão 1X2 via Poisson com Dixon-Coles."""
    mi = MatchInput(
        home=TeamInput(name="h", gf_avg=home_lambdas.get("gf_avg", 0),
                       ga_avg=home_lambdas.get("ga_avg", 0)),
        away=TeamInput(name="a", gf_avg=away_lambdas.get("gf_avg", 0),
                       ga_avg=away_lambdas.get("ga_avg", 0)),
    )
    return run_predict(mi, home_advantage=home_adv, rho=rho).probs["1x2"]
def backtest_league(league_id: int, home_adv: float = 1.15, window: int = 10,
                    feature: str = "xg", rho: float = 0.0) -> dict:
    """Backtest honesto: prevê cada jogo usando apenas os jogos anteriores.

    feature: 'xg' → usa xG marcado/sofrido; 'goals' → gols reais;
             'blend' → média simples dos dois (50% gols + 50% xG).
    rho: parâmetro Dixon-Coles (0 = Poisson puro, tipicamente ≈ -0.13).
    Retorna também `series`: curva de aprendizado real — acurácia acumulada
    a cada previsão (como o motor melhora conforme vê mais jogos).
    """
    matches = db.run_query(
        "SELECT m.id, m.kickoff_datetime, m.home_team_id, m.away_team_id, "
        "       m.xg_home, m.xg_away, m.score_home, m.score_away "
        "FROM matches m "
        "WHERE m.league_id=? AND m.status='played' AND m.score_home IS NOT NULL AND m.score_away IS NOT NULL "
        "  AND m.home_team_id IS NOT NULL AND m.away_team_id IS NOT NULL "
         "ORDER BY m.kickoff_datetime, m.id", (league_id,))
    if len(matches) < MIN_SAMPLES:
        return {"accuracy": 0.0, "brier": 0.0, "logloss": 0.0, "correct": 0, "total": len(matches),
                "series": [], "predictions": []}
    return backtest_completed_matches(matches, home_adv, window, feature, rho)
def backtest_completed_matches(matches, home_adv: float = 1.15, window: int = 10,
                               feature: str = "xg", rho: float = 0.0,
                               evaluation_start: int = 0) -> dict:
    """Backtest completed rows without querying the database.

    ``evaluation_start`` leaves earlier rows available as history while scoring
    only rows at or after that offset. It supports an honest final holdout.
    """
    matches = sorted(matches, key=lambda m: (m["kickoff_datetime"], m["id"]))
    if evaluation_start < 0 or evaluation_start > len(matches):
        raise ValueError("evaluation_start must be within the completed rows")

    hist: dict[int, deque] = {}
    correct = 0
    brier_sum = 0.0
    logloss_sum = 0.0
    total = 0
    series = []
    predictions = []

    index = 0
    while index < len(matches):
        kickoff = matches[index]["kickoff_datetime"]
        batch = []
        while index < len(matches) and matches[index]["kickoff_datetime"] == kickoff:
            batch.append(matches[index])
            index += 1
        # Fixtures at one kickoff are simultaneous: score every one before
        # their outcomes enter the history used by any other fixture.
        for batch_index, m in enumerate(batch, start=index - len(batch)):
            if batch_index < evaluation_start:
                continue
            hid, aid = m["home_team_id"], m["away_team_id"]
            hh, ah = hist.get(hid), hist.get(aid)
            if hh is None or ah is None or not hh or not ah:
                continue
            p = _predict_probs(_team_lambdas(hh, window, feature),
                               _team_lambdas(ah, window, feature), home_adv, rho)
            actual = "1" if m["score_home"] > m["score_away"] else ("X" if m["score_home"] == m["score_away"] else "2")
            correct += int(max(p, key=p.get) == actual)
            brier_sum += (1 - p[actual]) ** 2 + sum(p[k] ** 2 for k in p if k != actual)
            logloss_sum += -math.log(max(p[actual], 1e-10))
            total += 1
            series.append((total, correct / total * 100))
            # Keep only the evaluation facts needed for reproducible scoring.
            predictions.append({"match_id": m["id"], "actual": actual, "probabilities": dict(p)})
        for m in batch:
            hid, aid = m["home_team_id"], m["away_team_id"]
            gm = compute_match_stats({"score_home": m["score_home"], "score_away": m["score_away"], "xg_home": m["xg_home"], "xg_away": m["xg_away"]}, feature)
            hist.setdefault(hid, deque(maxlen=window)).appendleft({"gf": gm["gf"], "ga": gm["ga"]})
            hist.setdefault(aid, deque(maxlen=window)).appendleft({"gf": gm["ga"], "ga": gm["gf"]})

    if total == 0:
        return {"accuracy": 0.0, "brier": 0.0, "logloss": 0.0, "correct": 0, "total": 0,
                "series": [], "predictions": []}

    # amostra a cada ~5% dos jogos para uma curva suave (máx ~60 pontos)
    step = max(1, len(series) // 60)
    sampled = [{"n": n, "acc": round(acc, 1)} for i, (n, acc) in enumerate(series) if i % step == 0]
    if sampled and sampled[-1]["n"] != series[-1][0]:
        sampled.append({"n": series[-1][0], "acc": round(series[-1][1], 1)})
    return {
        "accuracy": round(correct / total * 100, 2),
        "brier": round(brier_sum / total, 4),
        "logloss": round(logloss_sum / total, 4),
        "correct": correct,
        "total": total,
        "series": sampled,
        "predictions": predictions,
    }
def walkforward_validation(league_id: int, window: int = 10,
                          home_advantage: float = 1.15,
                          rho: float = 0.0) -> dict:
    """Validação walk-forward: treina com dados do passado, testa com o futuro.

    REUTILIZA o motor do backtest_league (ML Skill v1.1 §20.1: proibido
    validador paralelo). O backtest honesto já É walk-forward: prevê cada
    jogo usando somente o histórico anterior dos dois times, via Feature
    Engine unificado e Brier multiclasse coerente.

    Mantém o contrato de resposta (accuracy, brier, series, n_folds).
    """
    bt = backtest_league(league_id, home_adv=home_advantage, window=window, rho=rho)
    return {
        "accuracy": bt["accuracy"],
        "brier": bt["brier"],
        "series": bt["series"],
        "n_folds": bt.get("total", 0),
    }
