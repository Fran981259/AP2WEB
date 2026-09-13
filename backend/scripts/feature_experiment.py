"""Experimento científico FASE 14 — Features contextuais (FEATURE-001).

Protocolo walk-forward honesto por liga:
  Variante BASE:   λ = média Janela (modelo calibrado atual)
  Variante REST:   λ × f_fadiga (rest_days)
  Variante FORM:   λ × f_momentum (saldo gols recente)
  Variante TEAM_HA:λ × f_mando próprio do time
  Variante ALL:    todos combinados

Critério de promoção (por liga):
  - Brier_variante < Brier_BASE - 0.005 E LogLoss_variante < LogLoss_BASE - 0.005

Uso:
  cd backend && .venv/bin/python -m scripts.feature_experiment [league_id...]
  (sem args = todas as ligas calibradas)
"""
from __future__ import annotations

import json
import math
import os
import sys
from collections import defaultdict
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import db  # noqa: E402
from app.context_features import (  # noqa: E402
    NEUTRAL, _clip, form_slope_factor, rest_days_factor, team_ha_factor,
)
from app.feature_engine import window_stats as _window_stats  # noqa: E402
from app.learning import MIN_SAMPLES  # noqa: E402
from app.model import (  # noqa: E402
    TeamInput, build_matrix, compute_lambdas, probabilities,
)

WARMUP_EXTRA = 5

# Forças default dos modificadores (bounded, conservadores)
K_REST = 0.15
K_FORM = 0.08
K_HA = 1.0

# Margens mínimas de ganho p/ promoção (mesmo critério rígido da FASE 13)
MIN_BRIER_GAIN = 0.005
MIN_LOGLOSS_GAIN = 0.005


def _get_calibrated_leagues() -> list[dict]:
    rows = db.run_query(
        "SELECT league_id, feature, window, home_advantage, "
        "       COALESCE(rho, 0.0) AS rho "
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


def _base_lambdas(home_mle, away_mle, ha):
    # Mesma fórmula do modelo de produção (compute_lambdas), sem toque no modelo.
    home = TeamInput(name="h", **home_mle)
    away = TeamInput(name="a", **away_mle)
    return compute_lambdas(home, away, ha)


def _run_variant(base_home, base_away, f_home, f_away):
    return round(base_home * f_home, 4), round(base_away * f_away, 4)


def _probs_for_lambdas(lh, la, rho):
    matrix = build_matrix(lh, la, rho)
    return probabilities(matrix)["1x2"]


def _outcome(score_home: int, score_away: int) -> str:
    return "1" if score_home > score_away else ("2" if score_home < score_away else "X")


def _brier(probs: dict, result_code: str) -> float:
    actual = {"1": 0.0, "X": 0.0, "2": 0.0}
    actual[result_code] = 1.0
    return sum((probs.get(k, 0) - actual[k]) ** 2 for k in actual)


def _logloss(probs: dict, result_code: str) -> float:
    p = max(min(probs.get(result_code, 0), 1 - 1e-15), 1e-15)
    return -math.log(p)


def _coerce_kickoff_ts(kickoff: Optional[str]) -> Optional[float]:
    if not kickoff:
        return None
    import datetime as dt
    try:
        return dt.datetime.fromisoformat(kickoff.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def run_experiment_league(league_id: int, model: dict) -> dict:
    matches = _load_matches(league_id)
    if len(matches) < MIN_SAMPLES:
        return {"league_id": league_id, "skipped": True,
                "total_matches": len(matches), "min_samples": MIN_SAMPLES}

    feature = model["feature"]
    window = model["window"]
    ha = model["home_advantage"]
    rho = model.get("rho", 0.0)

    warmup = max(window, 5) + WARMUP_EXTRA

    variants = ["base", "rest", "form", "team_ha", "all"]
    results = defaultdict(lambda: {"n": 0, "brier": 0.0, "logloss": 0.0, "correct": 0})

    for idx in range(warmup, len(matches)):
        current = matches[idx]
        history = matches[:idx]
        result_code = _outcome(current["score_home"], current["score_away"])
        kickoff_ts = _coerce_kickoff_ts(current.get("kickoff_datetime"))

        home_mle = _window_stats(history, current["home_team_id"], window, feature)
        away_mle = _window_stats(history, current["away_team_id"], window, feature)

        base_h, base_a = _base_lambdas(home_mle, away_mle, ha)

        # Modificadores
        as_of = current.get("kickoff_datetime")
        fr_home = rest_days_factor(league_id, current["home_team_id"], kickoff_ts, K_REST)
        fr_away = rest_days_factor(league_id, current["away_team_id"], kickoff_ts, K_REST)
        ff_home = form_slope_factor(league_id, current["home_team_id"], strength=K_FORM, as_of=as_of)
        ff_away = form_slope_factor(league_id, current["away_team_id"], strength=K_FORM, as_of=as_of)
        fha_home = NEUTRAL + K_HA * (team_ha_factor(league_id, current["home_team_id"], as_of=as_of) - NEUTRAL)
        fha_away = 1.0 / (NEUTRAL + K_HA * (team_ha_factor(league_id, current["away_team_id"], as_of=as_of) - NEUTRAL))

        lambdas_variants = {
            "base": (base_h, base_a),
            "rest": _run_variant(base_h, base_a, fr_home, fr_away),
            "form": _run_variant(base_h, base_a, ff_home, ff_away),
            "team_ha": _run_variant(base_h, base_a, _clip(fha_home), _clip(fha_away)),
            "all": _run_variant(base_h, base_a,
                                _clip(fr_home * ff_home * fha_home),
                                _clip(fr_away * ff_away * fha_away)),
        }

        for variant, (lh, la) in lambdas_variants.items():
            probs = _probs_for_lambdas(lh, la, rho)
            results[variant]["n"] += 1
            results[variant]["brier"] += _brier(probs, result_code)
            results[variant]["logloss"] += _logloss(probs, result_code)
            if max(probs, key=probs.get) == result_code:
                results[variant]["correct"] += 1

    out = {}
    for v, r in results.items():
        n = r["n"]
        out[v] = {
            "n": n,
            "brier": round(r["brier"] / n, 4),
            "logloss": round(r["logloss"] / n, 4),
            "accuracy": round(r["correct"] / n * 100, 2),
        }

    base = out["base"]
    best_variant = "base"
    best_gain = 0.0
    for v in ("rest", "form", "team_ha", "all"):
        gain = base["brier"] - out[v]["brier"]
        if gain > best_gain:
            best_gain = gain
            best_variant = v

    # Critério honesto (BASE.md §36): melhor que base em Brier E LogLoss,
    # com margem mínima rígida (igual FASE 13)
    promoted = (best_variant != "base"
                and best_gain >= MIN_BRIER_GAIN
                and base["logloss"] - out[best_variant]["logloss"] >= MIN_LOGLOSS_GAIN)

    return {
        "league_id": league_id,
        "skipped": False,
        "total_matches": len(matches),
        "tested": base["n"],
        "models": out,
        "best_variant": best_variant,
        "best_gain_brier": round(best_gain, 4),
        "promoted": promoted,
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
        print("Nenhuma liga calibrada.")
        return

    summary = {"experiments": [], "counts": defaultdict(int)}
    for model in models:
        lid = model["league_id"]
        try:
            result = run_experiment_league(lid, model)
        except Exception as e:
            print(f"[ERRO] liga {lid}: {e}")
            summary["experiments"].append({"league_id": lid, "skipped": True, "error": str(e)})
            continue
        summary["experiments"].append(result)
        if result.get("skipped"):
            print(f"[SKIP] liga {lid} — {result['total_matches']} jogos")
            continue
        summary["counts"][result["best_variant"]] += 1
        base = result["models"]["base"]
        bv = result["models"][result["best_variant"]]
        flag = "PROMO" if result["promoted"] else "----"
        print(f"[{flag}] liga {lid}: base={base['brier']:.4f}/{base['logloss']:.4f} | "
              f"best={result['best_variant']}={bv['brier']:.4f}/{bv['logloss']:.4f} "
              f"(gain {result['best_gain_brier']:+.4f})")

    print("\n=== RESUMO FASE 14 ===")
    tested = [e for e in summary["experiments"] if not e.get("skipped")]
    print(f"Ligas testadas: {len(tested)}")
    print("Melhor variante por liga:", dict(summary["counts"]))
    promoted = [e for e in tested if e.get("promoted")]
    print(f"Promovidas (gain >= {MIN_BRIER_GAIN} em Brier E LogLoss): {len(promoted)}")

    out_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "data",
                            "feature_experiment.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"Salvo em: {os.path.abspath(out_file)}")


if __name__ == "__main__":
    args = [int(a) for a in sys.argv[1:] if a.isdigit()]
    main(args if args else None)
