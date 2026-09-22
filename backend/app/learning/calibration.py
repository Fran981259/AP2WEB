"""Grid calibration, model registry reads and status views."""
from __future__ import annotations

from .. import db
from ..columns import LEAGUE_MODELS, prefixed
from .grids import (
    FEATURE_GRID,
    HOME_ADVANTAGE_GRID,
    MIN_SAMPLES,
    RHO_GRID,
    WINDOW_GRID,
    _PLAYED_COUNT,
)
from .walkforward import backtest_league


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
    _ensure_rho_column()
    _ensure_bayesian_columns()
    _ensure_context_columns()
    rows = db.run_query(f"SELECT {LEAGUE_MODELS} FROM league_models WHERE league_id=?", (league_id,))
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
    _ensure_rho_column()
    _ensure_bayesian_columns()
    _ensure_context_columns()
    rows = db.run_query(
        f"SELECT {prefixed(LEAGUE_MODELS, 'lm')}, l.name, "
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
    from .. import jobs

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
