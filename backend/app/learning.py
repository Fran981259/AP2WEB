"""Aprendizado e calibração do motor Poisson.

Ideia central: cada liga tem um "fator de mando" (home_advantage) e um tamanho de
janela deslizante ótimos, aprendidos dos resultados reais via BACKTEST HONESTO —
para prever o jogo N, usamos apenas os jogos 1..N-1 (sem vazamento de dados).

Métricas de avaliação:
  - Acurácia 1X2: % de jogos onde o favorito (maior prob.) acertou o resultado.
  - Brier score: erro quadrático médio entre as probs 1X2 e o resultado real
    (0 = perfeito, menor é melhor). Penaliza excesso de confiança.
"""
from __future__ import annotations

import threading
from collections import deque
from datetime import datetime

from . import db
from .model import MatchInput, TeamInput, predict as run_predict

# grade de fatores de mando e janelas testados na calibração
HOME_ADVANTAGE_GRID = [1.0, 1.05, 1.10, 1.15, 1.20, 1.25, 1.30]
WINDOW_GRID = [5, 8, 10, 12, 15]

MIN_SAMPLES = 40  # mínimo de jogos por liga para calibrar


def _team_lambdas(history: deque, window: int) -> dict:
    """λ (gf/ga médio) do time usando só os últimos `window` jogos da janela."""
    gf, ga = 0.0, 0.0
    n = 0
    for h in history:
        if n >= window:
            break
        gf += h["gf"]
        ga += h["ga"]
        n += 1
    if n == 0:
        return {"gf_avg": 1.2, "ga_avg": 1.2}
    return {"gf_avg": round(gf / n, 3), "ga_avg": round(ga / n, 3)}


def _predict_probs(home_lambdas: dict, away_lambdas: dict, home_adv: float) -> dict:
    """Retorna probs 1X2 do confronto (normalizadas)."""
    mi = MatchInput(
        home=TeamInput(name="h", **home_lambdas),
        away=TeamInput(name="a", **away_lambdas),
    )
    result = run_predict(mi, home_advantage=home_adv)
    return result.probs["1x2"]


def backtest_league(league_id: int, home_adv: float = 1.15, window: int = 10) -> dict:
    """Backtest honesto: prevê cada jogo usando apenas os jogos anteriores.

    Retorna: {accuracy, brier, correct, total}.
    """
    matches = db.run_query(
        "SELECT m.id, m.match_date, m.home_team_id, m.away_team_id, "
        "       m.ft_home, m.ft_away "
        "FROM matches m "
        "WHERE m.league_id=? AND m.status='played' AND m.ft_home IS NOT NULL "
        "  AND m.home_team_id IS NOT NULL AND m.away_team_id IS NOT NULL "
        "ORDER BY m.match_date, m.id", (league_id,))
    if len(matches) < MIN_SAMPLES:
        return {"accuracy": 0.0, "brier": 0.0, "correct": 0, "total": len(matches)}

    # janelas por time (apenas jogos anteriores ao atual)
    hist: dict[int, deque] = {}
    correct = 0
    brier_sum = 0.0
    total = 0

    for m in matches:
        hid, aid = m["home_team_id"], m["away_team_id"]
        hh = hist.get(hid)
        ah = hist.get(aid)
        # precisa de histórico dos dois times
        if hh is not None and ah is not None and len(hh) > 0 and len(ah) > 0:
            home_l = _team_lambdas(hh, window)
            away_l = _team_lambdas(ah, window)
            p = _predict_probs(home_l, away_l, home_adv)
            actual = "1" if m["ft_home"] > m["ft_away"] else ("X" if m["ft_home"] == m["ft_away"] else "2")
            fav = max(p, key=p.get)
            if fav == actual:
                correct += 1
            brier_sum += (1 - p[actual]) ** 2 + sum(p[k] ** 2 for k in p if k != actual)
            total += 1
        # registra o resultado real nas janelas (só depois de usar como histórico)
        hh = hist.setdefault(hid, deque(maxlen=window))
        ah = hist.setdefault(aid, deque(maxlen=window))
        hh.appendleft({"gf": m["ft_home"], "ga": m["ft_away"]})
        ah.appendleft({"gf": m["ft_away"], "ga": m["ft_home"]})

    if total == 0:
        return {"accuracy": 0.0, "brier": 0.0, "correct": 0, "total": 0}
    return {
        "accuracy": round(correct / total * 100, 2),
        "brier": round(brier_sum / total, 4),
        "correct": correct,
        "total": total,
    }


def calibrate_league(league_id: int) -> dict | None:
    """Procura a combinação (home_advantage, window) com melhor Brier/accuracy."""
    best = None
    for window in WINDOW_GRID:
        for ha in HOME_ADVANTAGE_GRID:
            res = backtest_league(league_id, ha, window)
            if res["total"] < MIN_SAMPLES:
                continue
            key = (res["brier"], -res["accuracy"])
            if best is None or key < best["key"]:
                best = {"key": key, "ha": ha, "window": window, **res}
    if not best:
        return None
    db.run_exec(
        "INSERT INTO league_models(league_id,home_advantage,window,accuracy,brier,"
        "sample_count,calibrated_at) VALUES(?,?,?,?,?,?,datetime('now')) "
        "ON CONFLICT(league_id) DO UPDATE SET "
        "home_advantage=excluded.home_advantage, window=excluded.window, "
        "accuracy=excluded.accuracy, brier=excluded.brier, "
        "sample_count=excluded.sample_count, calibrated_at=excluded.calibrated_at",
        (league_id, best["ha"], best["window"], best["accuracy"], best["brier"], best["total"]))
    return {
        "league_id": league_id,
        "home_advantage": best["ha"],
        "window": best["window"],
        "accuracy": best["accuracy"],
        "brier": best["brier"],
        "samples": best["total"],
    }


def calibrate_all() -> dict:
    """Calibra todas as ligas com dados suficientes. Retorna resumo."""
    leagues = db.run_query(
        "SELECT l.id, l.name, l.code, "
        " (SELECT COUNT(*) FROM matches m WHERE m.league_id=l.id AND m.status='played' "
        "  AND m.ft_home IS NOT NULL) AS played "
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
    """Parâmetros calibrados da liga (fallback para 1.15/10 sem calibração)."""
    rows = db.run_query("SELECT * FROM league_models WHERE league_id=?", (league_id,))
    if not rows:
        return {"league_id": league_id, "home_advantage": 1.15, "window": 10,
                "accuracy": None, "brier": None, "sample_count": 0, "calibrated_at": None}
    d = dict(rows[0])
    d["home_advantage"] = float(d.get("home_advantage") or 1.15)
    d["window"] = int(d.get("window") or 10)
    return d


def model_status() -> dict:
    """Lista o estado do aprendizado de todas as ligas."""
    rows = db.run_query(
        "SELECT lm.*, l.name, l.code, "
        " (SELECT COUNT(*) FROM matches m WHERE m.league_id=l.id AND m.status='played' "
        "  AND m.ft_home IS NOT NULL) AS played "
        "FROM league_models lm JOIN leagues l ON l.id=lm.league_id "
        "ORDER BY l.name")
    calibrated = [dict(r) for r in rows]
    return {
        "calibrated": calibrated,
        "calibrated_count": len(calibrated),
        "grid": {"home_advantage": HOME_ADVANTAGE_GRID, "window": WINDOW_GRID},
        "min_samples": MIN_SAMPLES,
    }


# --------------------------------------------------------------------------
# Job de calibração em background (para não travar o request HTTP)
# --------------------------------------------------------------------------

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
    leagues = db.run_query(
        "SELECT l.id, l.name, l.code, "
        " (SELECT COUNT(*) FROM matches m WHERE m.league_id=l.id AND m.status='played' "
        "  AND m.ft_home IS NOT NULL) AS played "
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
            r = calibrate_league(lg["id"])
            if r:
                with _cal_state["lock"]:
                    _cal_state["results"].append({**r, "name": lg["name"]})
        with _cal_state["lock"]:
            _cal_state["done"] += 1
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