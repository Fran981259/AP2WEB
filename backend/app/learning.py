"""Aprendizado e calibração do motor Poisson (fonte: Sofascore).

Cada liga tem um "fator de mando" (home_advantage), uma janela deslizante e a
feature usada (xG ou gols reais) ótimos, aprendidos via BACKTEST HONESTO —
para prever o jogo N, usamos apenas os jogos 1..N-1 (sem vazamento de dados).

Métricas:
  - Acurácia 1X2: % de jogos onde o favorito (maior prob.) acertou o resultado.
  - Brier score: erro quadrático médio entre probs 1X2 e resultado real
    (0 = perfeito, menor é melhor). Penaliza excesso de confiança.

Dependência: Feature Engine — única fonte de features (gf, ga, xg, xga, window, blend).
"""
from __future__ import annotations

import math
import threading
from collections import deque
from datetime import datetime

from . import db
from .feature_engine import compute_team_stats, compute_match_stats
from .model import MatchInput, TeamInput, predict as run_predict

HOME_ADVANTAGE_GRID = [1.0, 1.05, 1.10, 1.15, 1.20, 1.25, 1.30]
WINDOW_GRID = [5, 8, 10, 12, 15]

MIN_SAMPLES = 30  # mínimo de jogos por liga para calibrar
FEATURE_GRID = ["xg", "goals", "blend"]  # features disponíveis para calibração


_PLAYED_COUNT = (
    "(SELECT COUNT(*) FROM matches m WHERE m.league_id={alias}.id "
    "AND m.status='played' AND m.score_home IS NOT NULL)"
)

def _team_lambdas(history: deque, window: int, feature: str) -> dict:
    """λ (médio) do tempo usando os últimos `window` jogos da janela.

    Agora delega ao Feature Engine para garantir consistência com prediction.py.
    """
    return compute_team_stats(history, window, feature)


def _predict_probs(home_lambdas: dict, away_lambdas: dict, home_adv: float) -> dict:
    mi = MatchInput(
        home=TeamInput(name="h", gf_avg=home_lambdas.get("gf_avg", 0), ga_avg=home_lambdas.get("ga_avg", 0)),
        away=TeamInput(name="a", gf_avg=away_lambdas.get("gf_avg", 0), ga_avg=away_lambdas.get("ga_avg", 0)),
    )
    return run_predict(mi, home_advantage=home_adv).probs["1x2"]


def backtest_league(league_id: int, home_adv: float = 1.15, window: int = 10,
                    feature: str = "xg") -> dict:
    """Backtest honesto: prevê cada jogo usando apenas os jogos anteriores.

    feature: 'xg' → usa xG marcado/sofrido; 'goals' → gols reais;
             'blend' → média simples dos dois (50% gols + 50% xG).
    Retorna também `series`: curva de aprendizado real — acurácia acumulada
    a cada previsão (como o motor melhora conforme vê mais jogos).
    """
    matches = db.run_query(
        "SELECT m.id, m.kickoff_datetime, m.home_team_id, m.away_team_id, "
        "       m.xg_home, m.xg_away, m.score_home, m.score_away "
        "FROM matches m "
        "WHERE m.league_id=? AND m.status='played' "
        "  AND m.home_team_id IS NOT NULL AND m.away_team_id IS NOT NULL "
        "ORDER BY m.kickoff_datetime, m.id", (league_id,))
    if len(matches) < MIN_SAMPLES:
        return {"accuracy": 0.0, "brier": 0.0, "logloss": 0.0, "correct": 0, "total": len(matches),
                "series": []}

    hist: dict[int, deque] = {}
    correct = 0
    brier_sum = 0.0
    logloss_sum = 0.0
    total = 0
    series = []

    for m in matches:
        hid, aid = m["home_team_id"], m["away_team_id"]
        hh = hist.get(hid)
        ah = hist.get(aid)
        if hh is not None and ah is not None and len(hh) > 0 and len(ah) > 0:
            home_l = _team_lambdas(hh, window, feature)
            away_l = _team_lambdas(ah, window, feature)
            p = _predict_probs(home_l, away_l, home_adv)
            actual = "1" if m["score_home"] > m["score_away"] else (
                "X" if m["score_home"] == m["score_away"] else "2")
            fav = max(p, key=p.get)
            hit = int(fav == actual)
            correct += hit
            brier_sum += (1 - p[actual]) ** 2 + sum(p[k] ** 2 for k in p if k != actual)
            logloss_sum += -math.log(max(p[actual], 1e-10))
            total += 1
            series.append((total, correct / total * 100))
        # Usar Feature Engine para stats da partida (unificado com prediction.py)
        gm = compute_match_stats({
            "score_home": m["score_home"],
            "score_away": m["score_away"],
            "xg_home": m["xg_home"],
            "xg_away": m["xg_away"],
        }, feature)
        gh, ga = gm["gf"], gm["ga"]
        hh = hist.setdefault(hid, deque(maxlen=window))
        ah = hist.setdefault(aid, deque(maxlen=window))
        hh.appendleft({"gf": gh, "ga": ga})
        ah.appendleft({"gf": ga, "ga": gh})

    if total == 0:
        return {"accuracy": 0.0, "brier": 0.0, "logloss": 0.0, "correct": 0, "total": 0, "series": []}

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
    }


def calibrate_league(league_id: int) -> dict | None:
    """Procura a combinação (feature, home_advantage, window) com melhor Brier/accuracy."""
    best = None
    for feature in FEATURE_GRID:
        for window in WINDOW_GRID:
            for ha in HOME_ADVANTAGE_GRID:
                res = backtest_league(league_id, ha, window, feature)
                if res["total"] < MIN_SAMPLES:
                    continue
                key = (res["brier"], -res["accuracy"])
                if best is None or key < best["key"]:
                    best = {"key": key, "ha": ha, "window": window,
                            "feature": feature, **res}
    if not best:
        return None
    db.run_exec(
        "INSERT INTO league_models(league_id,home_advantage,window,feature,accuracy,brier,"
        "sample_count,calibrated_at) VALUES(?,?,?,?,?,?,?,datetime('now')) "
        "ON CONFLICT(league_id) DO UPDATE SET "
        "home_advantage=excluded.home_advantage, window=excluded.window, "
        "feature=excluded.feature, accuracy=excluded.accuracy, brier=excluded.brier, "
        "sample_count=excluded.sample_count, calibrated_at=excluded.calibrated_at",
        (league_id, best["ha"], best["window"], best["feature"],
         best["accuracy"], best["brier"], best["total"]))
    return {
        "league_id": league_id,
        "home_advantage": best["ha"],
        "window": best["window"],
        "feature": best["feature"],
        "accuracy": best["accuracy"],
        "brier": best["brier"],
        "samples": best["total"],
    }


def calibrate_all() -> dict:
    """Calibra todas as ligas com dados suficientes."""
    leagues = db.run_query(
        "SELECT l.id, l.name, "
        f" {_PLAYED_COUNT.format(alias='l')} AS played "
        "FROM leagues l ORDER BY l.name")
    done, skipped = [], []
    for lg in leagues:
        if lg["played"] < MIN_SAMPLES:
            skipped.append({"id": lg["id"], "name": lg["name"], "played": lg["played"]})
            continue
        r = calibrate_league(lg["id"])
        if r:
            done.append({**r, "name": lg["name"]})
    return {
        "calibrated": done,
        "skipped": skipped,
        "total_leagues": len(leagues),
        "calibrated_count": len(done),
    }


def get_model(league_id: int) -> dict:
    """Parâmetros calibrados da liga (fallback para xg/1.15/10 sem calibração)."""
    rows = db.run_query("SELECT * FROM league_models WHERE league_id=?", (league_id,))
    if not rows:
        return {"league_id": league_id, "home_advantage": 1.15, "window": 10,
                "feature": "xg", "accuracy": None, "brier": None,
                "sample_count": 0, "calibrated_at": None}
    d = dict(rows[0])
    d["home_advantage"] = float(d.get("home_advantage") or 1.15)
    d["window"] = int(d.get("window") or 10)
    d["feature"] = d.get("feature") or "xg"
    return d


def model_status() -> dict:
    rows = db.run_query(
        "SELECT lm.*, l.name, "
        f" {_PLAYED_COUNT.format(alias='l')} AS played "
        "FROM league_models lm JOIN leagues l ON l.id=lm.league_id "
        "ORDER BY l.name")
    return {
        "calibrated": [dict(r) for r in rows],
        "calibrated_count": len(rows),
        "grid": {"home_advantage": HOME_ADVANTAGE_GRID, "window": WINDOW_GRID,
                 "feature": FEATURE_GRID},
        "min_samples": MIN_SAMPLES,
    }


def motor_curve(buckets: int = 20) -> dict:
    """Linha de aprendizado real do motor: acurácia acumulada média por liga,
    alinhada por % de temporada (0→100%) e ponderada pelo nº de amostras."""
    leagues = db.run_query(
        "SELECT l.id, l.name, "
        f" {_PLAYED_COUNT.format(alias='l')} AS played "
        "FROM leagues l WHERE played >= ? ORDER BY l.name", (MIN_SAMPLES,))
    if not leagues:
        return {"series": [], "leagues": [], "total_played": 0}

    accs = [[] for _ in range(buckets)]
    weights = []
    per_league = []
    for lg in leagues:
        model = get_model(lg["id"])
        r = backtest_league(lg["id"], model["home_advantage"], model["window"],
                            model["feature"])
        if not r["series"]:
            continue
        # reamostra a série da liga para `buckets` pontos (por % de temporada)
        total = r["series"][-1]["n"] or 1
        pts = [0.0] * buckets
        for b in range(buckets):
            target = (b + 1) / buckets * total
            pts[b] = r["series"][-1]["acc"]
            for s in r["series"]:
                if s["n"] >= target:
                    pts[b] = s["acc"]
                    break
        for b in range(buckets):
            accs[b].append(pts[b])
        weights.append(r["total"])
        per_league.append({"id": lg["id"], "name": lg["name"],
                           "accuracy": r["accuracy"], "total": r["total"]})

    wsum = sum(weights) or 1
    series = [{
        "pct": round((b + 1) / buckets * 100),
        "acc": round(sum(a * w for a, w in zip(accs[b], weights)) / wsum, 1),
    } for b in range(buckets)]
    return {"series": series, "leagues": per_league,
            "total_played": sum(weights), "total_leagues": len(per_league)}


_cal_state = {
    "lock": threading.Lock(),
    "running": False,
    "done": 0,
    "total": 0,
    "current": "",
    "results": [],
    "skipped": [],
    "started_at": None,
    "finished_at": None,
}


def _run_calibration_job() -> None:
    try:
        leagues = db.run_query(
            "SELECT l.id, l.name, "
            f" {_PLAYED_COUNT.format(alias='l')} AS played "
            "FROM leagues l ORDER BY l.name")
        with _cal_state["lock"]:
            _cal_state.update(running=True, done=0, total=len(leagues), current="",
                              results=[], skipped=[], started_at=datetime.now().isoformat(),
                              finished_at=None)
        for lg in leagues:
            with _cal_state["lock"]:
                _cal_state["current"] = lg["name"]
            if lg["played"] < MIN_SAMPLES:
                with _cal_state["lock"]:
                    _cal_state["skipped"].append({"id": lg["id"], "name": lg["name"],
                                                  "played": lg["played"]})
            else:
                try:
                    r = calibrate_league(lg["id"])
                except Exception as e:
                    r = None
                    with _cal_state["lock"]:
                        _cal_state["skipped"].append({"id": lg["id"], "name": lg["name"],
                                                      "played": lg["played"], "error": str(e)[:120]})
                if r:
                    with _cal_state["lock"]:
                        _cal_state["results"].append({**r, "name": lg["name"]})
            with _cal_state["lock"]:
                _cal_state["done"] += 1
    except Exception as e:
        with _cal_state["lock"]:
            _cal_state["error"] = str(e)[:200]
    finally:
        with _cal_state["lock"]:
            _cal_state["running"] = False
            _cal_state["current"] = ""
            _cal_state["finished_at"] = datetime.now().isoformat()


def start_calibration() -> dict:
    with _cal_state["lock"]:
        if _cal_state["running"]:
            return {k: _cal_state[k] for k in ("running", "done", "total", "current")}
        thread = threading.Thread(target=_run_calibration_job, daemon=True)
        thread.start()
    return calibration_status()


def calibration_status() -> dict:
    with _cal_state["lock"]:
        return {k: _cal_state[k] for k in
                ("running", "done", "total", "current", "results", "skipped",
                 "started_at", "finished_at")}

def walkforward_validation(league_id: int, window: int = 10,
                          home_advantage: float = 1.15) -> dict:
    """Validação walk-forward: treina com dados do passado, testa com o futuro.

    REUTILIZA o motor do backtest_league (ML Skill v1.1 §20.1: proibido
    validador paralelo). O backtest honesto já É walk-forward: prevê cada
    jogo usando somente o histórico anterior dos dois times, via Feature
    Engine unificado e Brier multiclasse coerente.

    Mantém o contrato de resposta (accuracy, brier, series, n_folds).
    """
    bt = backtest_league(league_id, home_adv=home_advantage, window=window)
    return {
        "accuracy": bt["accuracy"],
        "brier": bt["brier"],
        "series": bt["series"],
        "n_folds": bt.get("total", 0),
    }
