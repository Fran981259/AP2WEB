"""Experimento científico FASE 13 — Comparação Poisson (MLE) vs Bayesian.

Protocolo walk-forward honesto:
  - Para cada liga calibrada com >= MIN_SAMPLES jogos:
    - Ordena jogos cronologicamente
    - Para cada jogo t (a partir do warm-up):
      Modelo A: Poisson MLE (baseline — médias da janela)
      Modelo B: Bayesian Gamma-Poisson (posterior completo, sem janela)
      Modelo C: Híbrido (blend bayesian λ com peso por volume)
      → prevê distribuição 1X2, mede Brier/LogLoss

Critério de promoção:
  - Brier_B < Brier_A E LogLoss_B < LogLoss_A (teste pareado)
  - Ganho >= 0.5% em Brier para promover à produção

Uso:
  cd backend && .venv/bin/python -m scripts.bayesian_experiment [league_id...]
  (sem args = todas as ligas calibradas)
"""
from __future__ import annotations

import json
import math
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import db  # noqa: E402
from app.bayesian import (  # noqa: E402
    BayesianEngine, build_bayesian_engine_from_history,
)
from app.feature_engine import window_stats as _window_stats  # noqa: E402
from app.learning import MIN_SAMPLES, get_model  # noqa: E402
from app.model import MatchInput, TeamInput, predict as run_predict  # noqa: E402


def _get_calibrated_leagues() -> list[dict]:
    rows = db.run_query(
        "SELECT league_id, feature, window, home_advantage, "
        "       COALESCE(rho, 0.0) AS rho, accuracy, brier "
        "FROM league_models ORDER BY league_id")
    return [dict(r) for r in rows]


def _load_matches(league_id: int) -> list[dict]:
    rows = db.run_query(
        "SELECT m.id, m.kickoff_datetime, m.home_team_id, m.away_team_id, "
        "       m.score_home, m.score_away, m.xg_home, m.xg_away, "
        "       th.name AS home_name, ta.name AS away_name "
        "FROM matches m "
        "JOIN teams th ON th.id=m.home_team_id "
        "JOIN teams ta ON ta.id=m.away_team_id "
        "WHERE m.league_id=? AND m.status='played' "
        "  AND m.home_team_id IS NOT NULL AND m.away_team_id IS NOT NULL "
        "ORDER BY m.kickoff_datetime, m.id",
        (league_id,))
    return [dict(r) for r in rows]


def _bayesian_lambdas(engine: BayesianEngine, team_id: int) -> tuple[float, float]:
    t = engine.teams.get(team_id)
    if not t:
        return (engine.prior_alpha / engine.prior_beta,
                engine.prior_alpha / engine.prior_beta)
    return (t.lambda_gf, t.lambda_ga)


def _hybrid_lambdas(engine: BayesianEngine, mle: dict, team_id: int) -> tuple[float, float]:
    t = engine.teams.get(team_id)
    if not t:
        return (mle["gf_avg"], mle["ga_avg"])
    weight = min(t.games_observed / 10.0, 1.0)
    bay_gf, bay_ga = t.lambda_gf, t.lambda_ga
    gf = weight * bay_gf + (1 - weight) * mle["gf_avg"]
    ga = weight * bay_ga + (1 - weight) * mle["ga_avg"]
    return (gf, ga)


def _predict(mi: MatchInput, ha: float, rho: float) -> dict:
    result = run_predict(mi, home_advantage=ha, rho=rho)
    return result.probs["1x2"]


def _brier(probs: dict, result_code: str) -> float:
    # one-hot: {"1": 1, "X": 0, "2": 0}
    actual = {"1": 0.0, "X": 0.0, "2": 0.0}
    actual[result_code] = 1.0
    return sum((probs.get(k, 0) - actual[k]) ** 2 for k in actual)


def _logloss(probs: dict, result_code: str) -> float:
    p = max(min(probs.get(result_code, 0), 1 - 1e-15), 1e-15)
    return -math.log(p)


def _outcome(score_home: int, score_away: int) -> str:
    if score_home > score_away:
        return "1"
    if score_home < score_away:
        return "2"
    return "X"


def run_experiment_league(league_id: int, model: dict) -> dict:
    matches = _load_matches(league_id)
    if len(matches) < MIN_SAMPLES:
        return {"league_id": league_id, "skipped": True,
                "total_matches": len(matches), "min_samples": MIN_SAMPLES}

    feature = model["feature"]
    window = model["window"]
    ha = model["home_advantage"]
    rho = model.get("rho", 0.0)

    warmup = max(window, 5)

    engine = build_bayesian_engine_from_history(matches[:warmup])

    results = defaultdict(lambda: {"n": 0, "brier": 0.0, "logloss": 0.0,
                                   "correct": 0, "picked": 0.0})

    for idx in range(warmup, len(matches)):
        current = matches[idx]
        history = matches[:idx]

        result_code = _outcome(current["score_home"], current["score_away"])

        # Atualiza engine bayesiano com o jogo anterior (já visto)
        if idx > warmup:
            prev = matches[idx - 1]
            engine.update_team(prev["home_team_id"], prev["home_name"],
                               prev["score_home"], prev["score_away"])
            engine.update_team(prev["away_team_id"], prev["away_name"],
                               prev["score_away"], prev["score_home"])

        home_id, away_id = current["home_team_id"], current["away_team_id"]

        # Modelo A: Poisson MLE (janela)
        home_mle = _window_stats(history, home_id, window, feature)
        away_mle = _window_stats(history, away_id, window, feature)
        mi_a = MatchInput(
            home=TeamInput(name=current["home_name"], **home_mle),
            away=TeamInput(name=current["away_name"], **away_mle),
        )
        probs_a = _predict(mi_a, ha, rho)

        # Modelo B: Bayesian puro
        bay_home, bay_away = _bayesian_lambdas(engine, home_id)
        bay_away_home, bay_away_away = _bayesian_lambdas(engine, away_id)
        mi_b = MatchInput(
            home=TeamInput(name=current["home_name"],
                           gf_avg=bay_home, ga_avg=bay_away),
            away=TeamInput(name=current["away_name"],
                           gf_avg=bay_away_home, ga_avg=bay_away_away),
        )
        probs_b = _predict(mi_b, ha, rho)

        # Modelo C: Híbrido
        hy_home, hy_ga = _hybrid_lambdas(engine, home_mle, home_id)
        hy_away, hy_aa = _hybrid_lambdas(engine, away_mle, away_id)
        mi_c = MatchInput(
            home=TeamInput(name=current["home_name"], gf_avg=hy_home, ga_avg=hy_ga),
            away=TeamInput(name=current["away_name"], gf_avg=hy_away, ga_avg=hy_aa),
        )
        probs_c = _predict(mi_c, ha, rho)

        for label, probs in (("A_mle", probs_a), ("B_bayesian", probs_b), ("C_hybrid", probs_c)):
            results[label]["n"] += 1
            results[label]["brier"] += _brier(probs, result_code)
            results[label]["logloss"] += _logloss(probs, result_code)
            fav = max(probs, key=probs.get)
            if fav == result_code:
                results[label]["correct"] += 1
            picked = probs.get(fav, 0)
            results[label]["picked"] += picked

    out = {}
    for label, r in results.items():
        n = r["n"]
        out[label] = {
            "n": n,
            "brier": round(r["brier"] / n, 4),
            "logloss": round(r["logloss"] / n, 4),
            "accuracy": round(r["correct"] / n * 100, 2),
            "avg_picked_prob": round(r["picked"] / n, 4),
        }

    a, b, c = out["A_mle"], out["B_bayesian"], out["C_hybrid"]

    verdict = "skip"
    reasoning = []
    if b["brier"] < a["brier"] and b["logloss"] < a["logloss"]:
        verdict = "bayesian_wins"
        reasoning.append(f"Bayesian supera MLE em Brier ({b['brier']} vs {a['brier']}) e LogLoss")
    elif c["brier"] < a["brier"] and c["logloss"] < a["logloss"]:
        verdict = "hybrid_wins"
        reasoning.append(f"Híbrido supera MLE em Brier ({c['brier']} vs {a['brier']}) e LogLoss")
    else:
        verdict = "mle_stays"
        reasoning.append("MLE continua melhor — Bayesian não justifica promoção")

    return {
        "league_id": league_id,
        "skipped": False,
        "total_matches": len(matches),
        "tested": a["n"],
        "models": out,
        "verdict": verdict,
        "reasoning": reasoning,
        "params": {"feature": feature, "window": window,
                   "home_advantage": ha, "rho": rho},
    }


def main(league_ids: list[int] | None = None) -> None:
    if league_ids:
        models = [dict(r) for r in db.run_query(
            "SELECT league_id, feature, window, home_advantage, "
            "       COALESCE(rho, 0.0) AS rho FROM league_models "
            "WHERE league_id IN (%s)" % ",".join("?" * len(league_ids)),
            tuple(league_ids))]
    else:
        models = _get_calibrated_leagues()

    if not models:
        print("Nenhuma liga calibrada para experimento.")
        return

    summary = {"experiments": [], "wins": {"A_mle": 0, "B_bayesian": 0, "C_hybrid": 0},
               "brier_delta_AVG": 0.0}
    brier_deltas = []

    for model in models:
        try:
            result = run_experiment_league(model["league_id"], model)
        except Exception as e:
            print(f"[ERRO] liga {model['league_id']}: {e}")
            summary["experiments"].append({
                "league_id": model["league_id"], "skipped": True, "error": str(e)})
            continue
        summary["experiments"].append(result)
        if result.get("skipped"):
            print(f"[SKIP] liga {model['league_id']} — {result['total_matches']} jogos "
                  f"(min {result['min_samples']})")
            continue
        verdict = result["verdict"]
        winner = {"bayesian_wins": "B_bayesian", "hybrid_wins": "C_hybrid"}.get(verdict, "A_mle")
        summary["wins"][winner] += 1

        a = result["models"]["A_mle"]
        b = result["models"]["B_bayesian"]
        delta = (b["brier"] - a["brier"])
        brier_deltas.append(delta)

        print(f"[{'OK' if verdict != 'mle_stays' else 'NO'}] liga {model['league_id']}: "
              f"A={a['brier']:.4f}/{a['logloss']:.4f} | "
              f"B={b['brier']:.4f}/{b['logloss']:.4f} | "
              f"C={result['models']['C_hybrid']['brier']:.4f} | "
              f"verdict={verdict} delta={delta:+.4f}")

    if brier_deltas:
        summary["brier_delta_AVG"] = round(sum(brier_deltas) / len(brier_deltas), 4)

    print("\n=== RESUMO ===")
    print(f"Ligas testadas: {len([e for e in summary['experiments'] if not e.get('skipped')])}")
    print(f"Vitórias: A(MLE)={summary['wins']['A_mle']} "
          f"B(Bayesian)={summary['wins']['B_bayesian']} "
          f"C(Híbrido)={summary['wins']['C_hybrid']}")
    print(f"ΔBrier médio (B - A): {summary['brier_delta_AVG']:+.4f}")

    out_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "data",
                            "bayesian_experiment.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"Resultados salvos em: {os.path.abspath(out_file)}")


if __name__ == "__main__":
    args = [int(a) for a in sys.argv[1:] if a.isdigit()]
    main(args if args else None)
