"""Aprendizado e calibração do motor Poisson + Dixon-Coles (fonte: Sofascore).

Cada liga tem:
  - home_advantage: fator de mando calibrado
  - window: janela deslizante ótima
  - feature: xG, gols ou blend
  - rho: parâmetro de dependência Dixon-Coles (0 = Poisson puro)

Calibração via BACKTEST HONESTO — para prever o jogo N, usamos apenas
os jogos 1..N-1 (sem vazamento de dados). Grid search otimiza Brier score
sobre (feature × window × home_advantage × rho).

Métricas:
  - Acurácia 1X2: % de jogos onde o favorito acertou o resultado.
  - Brier score: erro quadrático médio (0 = perfeito).
  - Log Loss: penalização por confiança incorreta.
"""
from __future__ import annotations

import math
from collections import deque

from . import db
from .feature_engine import compute_team_stats, compute_match_stats
from .model import MatchInput, TeamInput, predict as run_predict

HOME_ADVANTAGE_GRID = [1.05, 1.10, 1.15, 1.20, 1.25, 1.30]
WINDOW_GRID = [5, 10, 15]
RHO_GRID = [0.0, -0.05, -0.10, -0.13, -0.15, -0.20]  # Dixon-Coles param

MIN_SAMPLES = 20  # mínimo de previsões por liga para calibrar
FEATURE_GRID = ["xg", "goals", "blend"]  # features disponíveis para calibração


_PLAYED_COUNT = (
    "(SELECT COUNT(*) FROM matches m WHERE m.league_id={alias}.id "
    "AND m.status='played' AND m.score_home IS NOT NULL AND m.score_away IS NOT NULL)"
)

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


def calibrate_league(league_id: int) -> dict | None:
    """Procura a combinação (feature, window, ha, rho) com melhor Brier.

    Grid: 3 features × 3 windows × 6 ha × 6 rho = 324 combos por liga.
    Seleção por Brier score (menor = melhor), desempate por accuracy.
    """
    best = None
    for feature in FEATURE_GRID:
        for window in WINDOW_GRID:
            for ha in HOME_ADVANTAGE_GRID:
                for rho in RHO_GRID:
                    res = backtest_league(league_id, ha, window, feature, rho)
                    if res["total"] < MIN_SAMPLES:
                        continue
                    key = (res["brier"], -res["accuracy"])
                    if best is None or key < best["key"]:
                        best = {"key": key, "ha": ha, "window": window,
                                "feature": feature, "rho": rho, **res}
    if not best:
        return None

    rho_val = best.get("rho", 0.0)

    # Atualizar schema: adicionar coluna rho se não existir
    _ensure_rho_column()
    _ensure_bayesian_columns()

    db.run_exec(
        "INSERT INTO league_models(league_id,home_advantage,window,feature,rho,accuracy,brier,"
        "sample_count,calibrated_at) VALUES(?,?,?,?,?,?,?,?,datetime('now')) "
        "ON CONFLICT(league_id) DO UPDATE SET "
        "home_advantage=excluded.home_advantage, window=excluded.window, "
        "feature=excluded.feature, rho=excluded.rho, "
        "accuracy=excluded.accuracy, brier=excluded.brier, "
        "sample_count=excluded.sample_count, calibrated_at=excluded.calibrated_at",
        (league_id, best["ha"], best["window"], best["feature"],
         rho_val, best["accuracy"], best["brier"], best["total"]))
    return {
        "league_id": league_id,
        "home_advantage": best["ha"],
        "window": best["window"],
        "feature": best["feature"],
        "rho": rho_val,
        "accuracy": best["accuracy"],
        "brier": best["brier"],
        "samples": best["total"],
    }


def _ensure_rho_column() -> None:
    """Adiciona coluna rho à tabela league_models se não existir (migração leve)."""
    try:
        if db.MODE == "sqlite":
            cols = [r[1] for r in db.run_query("PRAGMA table_info(league_models)")]
            if "rho" not in cols:
                db.run_exec("ALTER TABLE league_models ADD COLUMN rho REAL DEFAULT 0.0")
        else:
            db.run_exec(
                "ALTER TABLE league_models ADD COLUMN IF NOT EXISTS rho REAL DEFAULT 0.0")
    except Exception:
        pass  # coluna já existe ou outro erro tolerável


def _ensure_bayesian_columns() -> None:
    """Adiciona colunas bayesian/method à league_models se não existirem (FASE 13)."""
    try:
        if db.MODE == "sqlite":
            cols = [r[1] for r in db.run_query("PRAGMA table_info(league_models)")]
            if "bayesian" not in cols:
                db.run_exec("ALTER TABLE league_models ADD COLUMN bayesian INTEGER DEFAULT 0")
            if "method" not in cols:
                db.run_exec("ALTER TABLE league_models ADD COLUMN method TEXT DEFAULT 'poisson'")
        else:
            db.run_exec(
                "ALTER TABLE league_models ADD COLUMN IF NOT EXISTS bayesian INTEGER DEFAULT 0")
            db.run_exec(
                "ALTER TABLE league_models ADD COLUMN IF NOT EXISTS method TEXT DEFAULT 'poisson'")
    except Exception:
        pass  # colunas já existem ou outro erro tolerável


def _ensure_context_columns() -> None:
    """Adiciona colunas ctx_*/contexto à league_models (FASE 14, FEATURE-001)."""
    try:
        if db.MODE == "sqlite":
            cols = [r[1] for r in db.run_query("PRAGMA table_info(league_models)")]
            for c in ("ctx_rest", "ctx_form", "ctx_team_ha"):
                if c not in cols:
                    db.run_exec(f"ALTER TABLE league_models ADD COLUMN {c} INTEGER DEFAULT 0")
        else:
            for c in ("ctx_rest", "ctx_form", "ctx_team_ha"):
                db.run_exec(f"ALTER TABLE league_models ADD COLUMN IF NOT EXISTS {c} INTEGER DEFAULT 0")
    except Exception:
        pass  # colunas já existem ou outro erro tolerável


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
    """Parâmetros calibrados da liga (fallback para xg/1.15/10/rho=0 sem calibração)."""
    _ensure_bayesian_columns()
    _ensure_context_columns()
    rows = db.run_query("SELECT * FROM league_models WHERE league_id=?", (league_id,))
    if not rows:
        return {"league_id": league_id, "home_advantage": 1.15, "window": 10,
                "feature": "xg", "rho": 0.0, "accuracy": None, "brier": None,
                "sample_count": 0, "calibrated_at": None,
                "bayesian": 0, "method": "poisson"}
    d = dict(rows[0])
    d["home_advantage"] = float(d.get("home_advantage") or 1.15)
    d["window"] = int(d.get("window") or 10)
    d["feature"] = d.get("feature") or "xg"
    d["rho"] = float(d.get("rho") or 0.0)
    d["bayesian"] = int(d.get("bayesian") or 0)
    d["method"] = d.get("method") or ("bayesian" if d["bayesian"] else "poisson")
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
                 "feature": FEATURE_GRID, "rho": RHO_GRID},
        "min_samples": MIN_SAMPLES,
    }


def motor_curve(buckets: int = 20) -> dict:
    """Linha de aprendizado real do motor: acurácia acumulada média por liga,
    alinhada por % de temporada (0→100%) e ponderada pelo nº de amostras."""
    # PostgreSQL does not allow a SELECT alias (``played``) in the same
    # statement's WHERE clause.  SQLite happened to accept the old query,
    # masking the defect until the production PostgreSQL deployment.
    leagues = db.run_query(
        "SELECT id, name, played FROM ("
        "SELECT l.id, l.name, "
        f" {_PLAYED_COUNT.format(alias='l')} AS played "
        "FROM leagues l"
        ") eligible WHERE played >= ? ORDER BY name", (MIN_SAMPLES,))
    if not leagues:
        return {"series": [], "leagues": [], "total_played": 0}

    accs = [[] for _ in range(buckets)]
    weights = []
    per_league = []
    for lg in leagues:
        model = get_model(lg["id"])
        r = backtest_league(lg["id"], model["home_advantage"], model["window"],
                            model["feature"], model.get("rho", 0.0))
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


def calibration_status() -> dict:
    """Read-only compatibility status backed by the durable jobs table."""
    from . import jobs

    recent = jobs.list_jobs(limit=10, job_type="calibrate_all")
    recent.extend(jobs.list_jobs(limit=10, job_type="calibrate_league"))
    recent.sort(key=lambda j: j.get("id", 0), reverse=True)
    active = [j for j in recent if j.get("status") in ("pending", "running")]
    last = recent[0] if recent else None
    done = sum(int(j.get("progress") or 0) for j in recent)
    total = max(len(recent), 1)
    results = []
    skipped = []
    for j in recent:
        results = results or []
        if j.get("status") == "completed" and isinstance(j.get("result"), dict):
            results.append(j["result"])
        for s in (j.get("result") or {}).get("skipped", []) if isinstance(j.get("result"), dict) else []:
            skipped.append(s) if s not in skipped else None
    return {
        "running": bool(active),
        "done": done,
        "total": total,
        "current": active[0].get("parameters", "") if active else "",
        "results": results,
        "skipped": skipped[:200],
        "started_at": last.get("started_at") if last else None,
        "finished_at": last.get("finished_at") if last else None,
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
