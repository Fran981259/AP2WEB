"""AP2WEB — API FastAPI.

Fonte única de dados: Sofascore.
Endpoints:
  POST /api/register            cadastro de usuário
  POST /api/login               login → JWT
  POST /api/sofascore/sync      sincroniza todas as ligas (background)
  GET  /api/sofascore/status    estado da sincronização
  GET  /api/sofascore/data      jogos + stats do banco
  GET  /api/leagues             ligas no banco (autenticado)
  GET  /api/leagues/{id}/matches  partidas da liga (autenticado)
  GET  /api/leagues/{id}/teams  times da liga (autenticado)
  GET  /api/matches/{id}/prediction  previsão Poisson (autenticado)
  GET  /api/leagues/{id}/predictions  próximas previsões (autenticado)
  POST /api/predict/fixture     previsão de confronto arbitrário
  GET  /api/learning/status     estado dos modelos calibrados
  POST /api/learning/calibrate  recalibra todas as ligas (background)
  GET  /api/learning/backtest/{league_id}  reavalia uma liga
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import db, sofascore_data
from .auth import authenticate, create_user, current_user
from .history import delete_prediction, list_predictions, save_prediction, stats
from .learning import (backtest_league, calibrate_league, calibration_status,
                       model_status, motor_curve, start_calibration)
from .prediction import predict_league_upcoming, predict_match, predict_fixture

app = FastAPI(title="AP2WEB", version="0.2.0")

_origins = [o.strip() for o in os.environ.get(
    "AP2WEB_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,https://app.theprostatereview.com").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    db.init_db()


class RegisterBody(BaseModel):
    username: str
    password: str


class LoginBody(BaseModel):
    username: str
    password: str


class FixtureBody(BaseModel):
    league_id: int
    home_team_id: int
    away_team_id: int


class PredictionBody(BaseModel):
    league_id: int
    match_id: int | None = None
    home_team_id: int
    away_team_id: int
    home_name: str
    away_name: str
    match_date: str | None = None
    pick_type: str
    pick_value: str
    pick_label: str
    prob: float
    odd: float
    payload: dict = {}


@app.post("/api/register", tags=["auth"])
def register(body: RegisterBody):
    create_user(body.username, body.password)
    return {"ok": True, "message": "Usuário criado"}


@app.post("/api/login", tags=["auth"])
def login(body: LoginBody):
    return authenticate(body.username, body.password)


@app.get("/api/me", tags=["auth"])
def me(user: str = Depends(current_user)):
    return {"username": user}


# --------------------------- dados (Sofascore) ---------------------------

@app.post("/api/sofascore/sync", tags=["sofascore"])
def sofascore_sync(user: str = Depends(current_user)):
    """Sincroniza todas as ligas configuradas (temporada + rodadas + stats) em background."""
    return sofascore_data.start_sync()


@app.post("/api/sofascore/sync/league/{league_id}", tags=["sofascore"])
def sofascore_sync_league(league_id: int, user: str = Depends(current_user)):
    """Sincroniza apenas uma liga (demanda pontual de dados)."""
    try:
        return sofascore_data.sync_league_local(league_id)
    except IndexError:
        raise HTTPException(status_code=404, detail="Liga não encontrada")


@app.get("/api/sofascore/status", tags=["sofascore"])
def sofascore_status(user: str = Depends(current_user)):
    return sofascore_data.status()


@app.get("/api/sofascore/data", tags=["sofascore"])
def sofascore_data_endpoint(league_id: int | None = None, user: str = Depends(current_user)):
    return sofascore_data.dataset(league_id)


@app.get("/api/leagues", tags=["data"])
def leagues(user: str = Depends(current_user)):
    return sofascore_data.leagues()


@app.get("/api/leagues/{league_id}/teams", tags=["data"])
def league_teams(league_id: int, user: str = Depends(current_user)):
    return [dict(r) for r in db.run_query(
        "SELECT t.id, t.name, "
        "(SELECT COUNT(*) FROM matches m WHERE (m.home_team_id=t.id OR m.away_team_id=t.id) "
        "  AND m.league_id=? AND m.status='played') AS games_played "
        "FROM teams t WHERE t.league_id=? ORDER BY t.name",
        (league_id, league_id))]


@app.get("/api/leagues/{league_id}/matches", tags=["data"])
def league_matches(league_id: int, user: str = Depends(current_user)):
    return [dict(r) for r in db.run_query(
        "SELECT m.id, m.kickoff_datetime, m.round, m.status, m.score_home, m.score_away, "
        "m.xg_home, m.xg_away, th.name AS home, ta.name AS away "
        "FROM matches m JOIN teams th ON th.id=m.home_team_id "
        "JOIN teams ta ON ta.id=m.away_team_id "
        "WHERE m.league_id=? ORDER BY m.kickoff_datetime DESC, m.id LIMIT 200",
        (league_id,))]


@app.get("/api/matches/{match_id}/prediction", tags=["prediction"])
def prediction(match_id: int, user: str = Depends(current_user),
               as_of_timestamp: str | None = None):
    try:
        return predict_match(match_id, as_of_timestamp=as_of_timestamp)
    except IndexError:
        raise HTTPException(status_code=404, detail="Partida não encontrada")


@app.post("/api/predict/fixture", tags=["prediction"])
def fixture_prediction(body: FixtureBody, user: str = Depends(current_user),
                       as_of_timestamp: str | None = None):
    try:
        return predict_fixture(body.league_id, body.home_team_id, body.away_team_id,
                               as_of_timestamp=as_of_timestamp)
    except IndexError:
        raise HTTPException(status_code=404, detail="Confronto não encontrado")


@app.get("/api/leagues/{league_id}/predictions", tags=["prediction"])
def league_predictions(league_id: int, user: str = Depends(current_user),
                       as_of_timestamp: str | None = None):
    return predict_league_upcoming(league_id, as_of_timestamp=as_of_timestamp)


# --------------------------- histórico de previsões ---------------------------

def _user_id(username: str) -> int:
    row = db.run_query("SELECT id FROM users WHERE username=?", (username,))
    if not row:
        raise HTTPException(status_code=401, detail="Usuário não encontrado")
    return row[0]["id"]


@app.post("/api/predictions", tags=["prediction"])
def create_prediction(body: PredictionBody, user: str = Depends(current_user)):
    return save_prediction(_user_id(user), body.model_dump())


@app.get("/api/predictions", tags=["prediction"])
def get_predictions(user: str = Depends(current_user)):
    uid = _user_id(user)
    return {"stats": stats(uid), "items": list_predictions(uid)}


@app.delete("/api/predictions/{prediction_id}", tags=["prediction"])
def remove_prediction(prediction_id: int, user: str = Depends(current_user)):
    delete_prediction(_user_id(user), prediction_id)
    return {"ok": True}


# --------------------------- aprendizado / calibração ---------------------------

@app.post("/api/learning/calibrate", tags=["learning"])
def learning_calibrate(user: str = Depends(current_user)):
    return start_calibration()


@app.post("/api/learning/calibrate/{league_id}", tags=["learning"])
def learning_calibrate_league(league_id: int, user: str = Depends(current_user)):
    r = calibrate_league(league_id)
    if not r:
        raise HTTPException(status_code=400, detail="Liga sem dados suficientes")
    return r


@app.get("/api/learning/calibrate/status", tags=["learning"])
def learning_calibrate_status(user: str = Depends(current_user)):
    return calibration_status()


@app.get("/api/learning/status", tags=["learning"])
def learning_status(user: str = Depends(current_user)):
    return model_status()


@app.get("/api/learning/curve", tags=["learning"])
def learning_curve(user: str = Depends(current_user)):
    """Linha de aprendizado real do motor (acurácia acumulada média por % de temporada)."""
    return motor_curve()


@app.get("/api/learning/backtest/{league_id}", tags=["learning"])
def learning_backtest(league_id: int, user: str = Depends(current_user)):
    return backtest_league(league_id)


@app.get("/api/learning/xgb/{league_id}", tags=["learning"])
def learning_xgb_comparison(league_id: int, user: str = Depends(current_user)):
    """BASE.md §26-27: comparação honesta XGBoost vs Poisson (walk-forward temporal).

    Lenta (~1 min): retreina o XGB incrementalmente ao longo da temporada.
    Veredito segue critérios Brier/LogLoss; promoção é decisão humana.
    """
    from .xgb_engine import compare_models
    return compare_models(league_id)


@app.get("/api/market/{match_id}", tags=["market"])
def market_match(match_id: int, as_of: str | None = None,
                 user: str = Depends(current_user)):
    """FASE 10 — Market Engine: fair odds, market odds, EV para um jogo.

    - `as_of` (opcional): filtro de data para evitar lookahead (FASE 4).
    """
    from .market import market_for_match
    return market_for_match(match_id, as_of)


@app.get("/api/market/league/{league_id}", tags=["market"])
def market_league(league_id: int, limit: int = 20,
                  as_of: str | None = None,
                  user: str = Depends(current_user)):
    """FASE 10 — Market Engine: odds+EV para os próximos jogos de uma liga."""
    from .market import market_league
    return market_league(league_id, limit, as_of)


@app.get("/api/evolution/snapshot", tags=["evolution"])
def evolution_snapshot(user: str = Depends(current_user)):
    """Snapshot atual do rastreador de evolução (baseline + delta vs anterior).

    Leve: sem suíte selenium (regression_suite=None na UI; use o CLI para medi-la).
    Cada chamada grava a medição no histórico persistente (append-only).
    """
    from .evolution_tracker import (_snapshot, _load_baseline, _compare,
                                    _append_history, _history_count)
    current = _snapshot(skip_regression=True)
    baseline = _load_baseline()
    changes = _compare(current, baseline) if baseline else []
    current["api_health"] = True   # este endpoint respondendo = API online
    current["regression_suite"] = None  # selenium só existe em dev
    _append_history(current)  # persiste toda medição da UI
    return {
        "current": current,
        "baseline": baseline,
        "changes": changes,
        "stable": len(changes) == 0,
        "history_size": _history_count(),
        "env": "dev" if os.environ.get("AP2WEB_DEV") else "deploy",
    }


@app.get("/api/evolution/history", tags=["evolution"])
def evolution_history(limit: int = 50, user: str = Depends(current_user)):
    """Série temporal das medições persistentes (para gráfico de tendência)."""
    from .evolution_tracker import _load_history, _trend_series
    history = _load_history(limit)
    return {
        "count": len(history),
        "history": history,
        "series": _trend_series(history),
    }


@app.get("/api/health", tags=["misc"])
def health():
    return {"ok": True, "app": "AP2WEB", "db": str(db.DB_PATH)}


# --- frontend estático (produção tudo-em-um) — registrado POR ÚLTIMO ---
_FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIST / "assets"), name="assets")

    @app.get("/")
    def _index():
        return FileResponse(_FRONTEND_DIST / "index.html")

    @app.get("/{full_path:path}")
    def _spa(full_path: str):
        candidate = _FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_FRONTEND_DIST / "index.html")