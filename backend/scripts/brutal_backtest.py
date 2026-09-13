"""Backtest brutal com paridade de produção.

Para cada liga calibrada, prevê cada jogo jogado usando `prediction._build`
exatamente como a produção faria (feature, HA, janela, rho, method e ctx_*),
com `as_of=kickoff` — sem dados futuros.

Métricas: acurácia 1X2, Brier multiclasse, Log Loss, ECE (expected calibration
error) nos bins de confiança do favorito. Compara também com a base Poisson MLE
calibrada (learning.backtest_league), que era a métrica exibida no painel.

Uso:
    python scripts/brutal_backtest.py [--leagues 112,130] [--out app/data/brutal_backtest.json]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import db  # noqa: E402
from app.learning import backtest_league, get_model  # noqa: E402
from app.prediction import _build  # noqa: E402

ECBINS = [(float(i) / 10.0, float(i + 1) / 10.0) for i in range(10)]


def _ece(bin_conf: list[float], bin_true: list[float], bin_n: list[int]) -> float:
    tot = sum(bin_n)
    if tot == 0:
        return 0.0
    return round(sum(n / tot * abs(c - t) for n, c, t in zip(bin_n, bin_conf, bin_true)), 4)


def _round(x, n=4):
    return round(x, n)


def backtest_league_production(league_id: int, league_name: str) -> dict:
    matches = db.run_query(
        "SELECT m.id, m.league_id, m.kickoff_datetime, m.home_team_id, m.away_team_id, "
        "       m.score_home, m.score_away, th.name AS home_name, ta.name AS away_name "
        "FROM matches m "
        "JOIN teams th ON th.id=m.home_team_id "
        "JOIN teams ta ON ta.id=m.away_team_id "
        "WHERE m.league_id=? AND m.status='played' "
        "  AND m.home_team_id IS NOT NULL AND m.away_team_id IS NOT NULL "
        "  AND m.score_home IS NOT NULL "
        "  AND m.kickoff_datetime IS NOT NULL AND m.kickoff_datetime != '' "
        "  AND m.kickoff_datetime <= datetime('now') "
        "ORDER BY m.kickoff_datetime, m.id", (league_id,))

    correct = 0
    brier_sum = 0.0
    logloss_sum = 0.0
    total = 0
    bin_true = [0.0] * 10
    bin_conf = [0.0] * 10
    bin_n = [0] * 10
    prev_kickoff = None

    for m in matches:
        res = _build(m["league_id"], m["home_team_id"], m["away_team_id"],
                     m["home_name"], m["away_name"], league_name,
                     match=dict(m), as_of_timestamp=m["kickoff_datetime"])
        p = res["probs"]["1x2"]
        actual = "1" if m["score_home"] > m["score_away"] else (
            "X" if m["score_home"] == m["score_away"] else "2")
        fav = max(p, key=p.get)
        hit = int(fav == actual)
        correct += hit
        brier_sum += (1 - p[actual]) ** 2 + sum(p[k] ** 2 for k in p if k != actual)
        logloss_sum += -math.log(max(p[actual], 1e-10))
        total += 1
        fp = p[fav]
        b = min(int(fp * 10), 9)
        bin_n[b] += 1
        bin_conf[b] += fp
        bin_true[b] += hit
        prev_kickoff = m["kickoff_datetime"]

    if total == 0:
        return {"total": 0}

    conf = [c / n if n else 0.0 for c, n in zip(bin_conf, bin_n)]
    tru = [t / n if n else 0.0 for t, n in zip(bin_true, bin_n)]

    return {
        "total": total,
        "correct": correct,
        "accuracy": _round(correct / total * 100, 2),
        "brier": _round(brier_sum / total, 4),
        "logloss": _round(logloss_sum / total, 4),
        "ece": _ece(conf, tru, bin_n),
        "last_kickoff": prev_kickoff,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--leagues", help="IDs separados por vírgula (default: todas calibradas)")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "app" / "data" / "brutal_backtest.json"),
                    help="caminho do JSON de saída")
    args = ap.parse_args()

    rows = db.run_query("SELECT lm.league_id, l.name FROM league_models lm JOIN leagues l ON l.id=lm.league_id WHERE lm.home_advantage IS NOT NULL ORDER BY l.name")
    if args.leagues:
        ids = {int(x) for x in args.leagues.split(",")}
        rows = [r for r in rows if r["league_id"] in ids]

    results = []
    t0 = time.time()
    for idx, (league_id, name) in enumerate(rows, 1):
        model = get_model(league_id)
        t1 = time.time()
        prod = backtest_league_production(league_id, name)
        bt = backtest_league(league_id, model["home_advantage"], model["window"],
                             model["feature"], model.get("rho", 0.0))
        results.append({
            "league_id": league_id,
            "name": name,
            "method": model.get("method", "poisson"),
            "feature": model["feature"], "window": model["window"],
            "home_advantage": model["home_advantage"], "rho": model.get("rho", 0.0),
            "context": {"rest": model.get("ctx_rest", 0), "form": model.get("ctx_form", 0),
                        "team_ha": model.get("ctx_team_ha", 0)},
            "production": prod,
            "base": {"accuracy": bt["accuracy"], "brier": bt["brier"],
                     "logloss": bt["logloss"], "total": bt["total"]},
        })
        d = prod.get("total") or 0
        delta = None
        if d and bt["total"] and prod.get("brier") is not None:
            delta = prod["brier"] - bt["brier"]
        delta_s = f"{delta:+0.4f}" if delta is not None else "  n/a "
        print(f"[{idx}/{len(rows)}] {name} · {model.get('method','poisson')} · n={d} "
              f"acc={prod.get('accuracy')}% brier={prod.get('brier')} ll={prod.get('logloss')} "
              f"ece={prod.get('ece')} (Δbase={delta_s}) · {time.time()-t1:.1f}s", flush=True)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w") as f:
        json.dump({"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "leagues": results}, f, ensure_ascii=False, indent=1)
    print(f"\nsalvo em {args.out} · tempo total {time.time()-t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()