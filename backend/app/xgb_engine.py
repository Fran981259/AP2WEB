"""XGBoost Engine — modelo candidato contra o baseline Poisson (BASE.md §26-27).

Regras aplicadas (ML Skill v1.1 §20.1 + QA v1.1 §66-A):
- Mesma metodologia temporal do backtest_league: cada jogo é previsto usando
  SOMENTE o histórico anterior dos dois times (zero leakage).
- Features por time (nunca média global da liga).
- Comparação obrigatória com bases ingênas (prior empírico, sempre-casa).
- Métricas: acurácia do favorito, Brier multiclasse coerente, Log Loss.

O XGBoost NÃO substitui o Poisson: esta engine produz apenas a COMPARAÇÃO.
Promoção exige benefício mensurável em Brier/LogLoss/Calibração.
"""
from __future__ import annotations

import math
from collections import deque

import numpy as np
from xgboost import XGBClassifier

from . import db
from .learning import _team_lambdas, _predict_probs
from .feature_engine import compute_match_stats

LABELS = ("1", "X", "2")
MIN_HISTORY = 5          # mínimo de jogos de CADA time para avaliar um confronto
WINDOW = 10              # janela de forma (igual ao baseline Poisson)


def _result(sh: float, aw: float) -> str:
    return "1" if sh > aw else ("X" if sh == aw else "2")


def _points(gf: float, ga: float) -> float:
    return 3.0 if gf > ga else (1.0 if gf == ga else 0.0)


def build_dataset(league_id: int, window: int = WINDOW) -> list[dict]:
    """Percorre os jogos cronologicamente construindo features SÓ com passado.

    Retorna linhas na ordem temporal. Cada linha contém o vetor de features
    do confronto e o resultado real. Times com histórico < MIN_HISTORY são
    mantidos com flag `evaluable=False` (o Poisson também não os prevê bem).
    """
    rows = db.run_query(
        "SELECT m.id, m.kickoff_datetime, m.home_team_id, m.away_team_id, "
        "       m.score_home, m.score_away, m.xg_home, m.xg_away "
        "FROM matches m "
        "WHERE m.league_id=? AND m.status='played' AND m.score_home IS NOT NULL "
        "  AND m.home_team_id IS NOT NULL AND m.away_team_id IS NOT NULL "
        "ORDER BY m.kickoff_datetime, m.id", (league_id,))

    hist: dict[int, deque] = {}
    dataset: list[dict] = []

    def team_features(tid: int) -> dict | None:
        h = hist.get(tid)
        if not h or len(h) == 0:
            return None
        n = len(h)
        pts = sum(e["pts"] for e in h)
        return {
            "gf": sum(e["gf"] for e in h) / n,
            "ga": sum(e["ga"] for e in h) / n,
            "xgf": sum(e["xgf"] for e in h) / n,
            "xga": sum(e["xga"] for e in h) / n,
            "ppg": pts / n,
            "n": n,
        }

    for m in rows:
        hid, aid = m["home_team_id"], m["away_team_id"]
        fh = team_features(hid)
        fa = team_features(aid)
        sh, sa = float(m["score_home"]), float(m["score_away"])
        xh = m["xg_home"] if m["xg_home"] is not None else sh
        xa = m["xg_away"] if m["xg_away"] is not None else sa

        evaluable = fh is not None and fa is not None \
            and fh["n"] >= MIN_HISTORY and fa["n"] >= MIN_HISTORY

        dataset.append({
            "match_id": m["id"],
            "kickoff": m["kickoff_datetime"],
            "home_team_id": hid,
            "away_team_id": aid,
            "evaluable": evaluable,
            "actual": _result(sh, sa),
            # vetor de features (12): força ofensiva/defensiva gols+xG e forma
            "X": ([fh["gf"], fh["ga"], fh["xgf"], fh["xga"], fh["ppg"], fh["n"],
                   fa["gf"], fa["ga"], fa["xgf"], fa["xga"], fa["ppg"], fa["n"]]
                  if evaluable else None),
            # λs do Poisson para o MESMO instante (mesmo histórico)
            "hist_home": list(hist[hid]) if hid in hist else [],
            "hist_away": list(hist[aid]) if aid in hist else [],
        })

        # atualiza históricos DEPOIS de construir a linha (evita leakage)
        hh = hist.setdefault(hid, deque(maxlen=window))
        ah = hist.setdefault(aid, deque(maxlen=window))
        hh.append({"gf": sh, "ga": sa, "xgf": xh, "xga": xa, "pts": _points(sh, sa)})
        ah.append({"gf": sa, "ga": sh, "xgf": xa, "xga": xh, "pts": _points(sa, sh)})

    return dataset


def _metrics(rows: list[dict], key: str) -> dict:
    n = len(rows)
    if n == 0:
        return {"accuracy": 0.0, "brier": 0.0, "log_loss": 0.0, "n": 0}
    correct = sum(1 for r in rows if r[key]["fav"] == r["actual"])
    brier = sum((1 - r[key]["probs"][r["actual"]]) ** 2
                + sum(r[key]["probs"][k] ** 2 for k in LABELS if k != r["actual"])
                for r in rows) / n
    ll = sum(-math.log(max(r[key]["probs"][r["actual"]], 1e-12)) for r in rows) / n
    return {"accuracy": round(correct / n * 100, 2),
            "brier": round(brier, 4),
            "log_loss": round(ll, 4),
            "n": n}


def compare_models(league_id: int, window: int = WINDOW,
                   retrain_every: int = 5) -> dict:
    """Compara, no MESMO conjunto de confrontos e MESMO instante temporal:
    XGBoost vs Poisson vs prior empírico (base ingênua probabilística).

    retrain_every: retreina o XGB a cada N jogos (custo × honestidade).
    """
    ds = [r for r in build_dataset(league_id, window) if r["evaluable"]]
    if len(ds) < 30:
        return {"ok": False, "error": f"dados insuficientes ({len(ds)} confrontos)",
                "league_id": league_id}

    X_all = np.array([r["X"] for r in ds], dtype=float)
    y_all = np.array([LABELS.index(r["actual"]) for r in ds])

    evaluated: list[dict] = []
    last_trained_at = -1
    model = None

    for i, row in enumerate(ds):
        if i < MIN_HISTORY * 2:
            continue
        # ── Poisson: mesmo histórico, mesmo instante ──
        def selected(history):
            return [compute_match_stats({"score_home": h["gf"], "score_away": h["ga"],
                                         "xg_home": h["xgf"], "xg_away": h["xga"]}, "blend")
                    for h in reversed(history)]
        hl = _team_lambdas(selected(row["hist_home"]), window, "blend")
        al = _team_lambdas(selected(row["hist_away"]), window, "blend")
        poi = _predict_probs(
            {"gf_avg": hl.get("gf_avg", 1.2), "ga_avg": hl.get("ga_avg", 1.2)},
            {"gf_avg": al.get("gf_avg", 1.2), "ga_avg": al.get("ga_avg", 1.2)},
            1.15)

        # ── prior empírico (base ingênua probabilística) ──
        counts = np.bincount(y_all[:i], minlength=3)[:3]
        prior = counts / counts.sum()

        # ── XGBoost: treina só com passado, prevê este jogo ──
        if model is None or i - last_trained_at >= retrain_every:
            model = XGBClassifier(
                n_estimators=120, max_depth=3, learning_rate=0.08,
                subsample=0.9, colsample_bytree=0.9,
                reg_lambda=1.5, eval_metric="mlogloss",
                objective="multi:softprob", num_class=3)
            model.fit(X_all[:i], y_all[:i])
            last_trained_at = i
        pb = model.predict_proba(X_all[i:i + 1])[0]

        def norm(p):
            s = sum(float(v) for v in p)
            return {LABELS[j]: float(p[j]) / s for j in range(3)}

        evaluated.append({
            "actual": row["actual"],
            "poisson": {"probs": norm([poi[k] for k in LABELS]),
                        "fav": max(LABELS, key=lambda k: poi[k])},
            "xgb": {"probs": norm(pb),
                    "fav": LABELS[int(np.argmax(pb))]},
            "prior": {"probs": norm(prior),
                      "fav": LABELS[int(np.argmax(prior))]},
        })

    comparison = {
        "league_id": league_id,
        "window": window,
        "retrain_every": retrain_every,
        "min_history": MIN_HISTORY,
        "evaluated_matches": len(evaluated),
        "poisson": _metrics(evaluated, "poisson"),
        "xgboost": _metrics(evaluated, "xgb"),
        "prior_empirico": _metrics(evaluated, "prior"),
    }

    # veredito objetivo conforme BASE.md §27 (Brier/LogLoss)
    best = min(("poisson", "xgboost"),
               key=lambda k: comparison[k]["brier"] + comparison[k]["log_loss"])
    beats_baseline = comparison["xgboost"]["brier"] < comparison["poisson"]["brier"] \
        and comparison["xgboost"]["log_loss"] < comparison["poisson"]["log_loss"]
    comparison["veredito"] = {
        "melhor_brier_logloss": best,
        "xgboost_supera_poisson": bool(beats_baseline),
        "promocao_recomendada": False,  # promoção é decisão humana (BASE.md §26)
    }
    comparison["ok"] = True
    return comparison
