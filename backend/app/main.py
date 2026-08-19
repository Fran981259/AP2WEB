"""AP2WEB — API FastAPI.

Endpoints:
  POST /api/register            cadastro de usuário
  POST /api/login               login → JWT
  POST /api/scrape/today        raspa matches.asp (autenticado)
  POST /api/scrape/league/{code} raspa resultados de uma liga (autenticado)
  GET  /api/leagues             ligas no banco (autenticado)
  GET  /api/leagues/{id}/matches  partidas da liga (autenticado)
  GET  /api/matches/{id}/prediction  previsão Poisson (autenticado)
  GET  /api/runs                histórico de raspagens (autenticado)
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import db, scraper
from .auth import authenticate, create_user, current_user
from .history import delete_prediction, list_predictions, save_prediction, stats
from .prediction import predict_league_upcoming, predict_match, predict_fixture

app = FastAPI(title="AP2WEB", version="0.1.0")

# Origem(s) permitida(s) — separar por vírgula. Default: local dev.
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


class ScrapeLeagueBody(BaseModel):
    league: str


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


# --------------------------- scraping ---------------------------

@app.post("/api/scrape/today", tags=["scrape"])
def scrape_today(user: str = Depends(current_user)):
    try:
        return scraper.scrape_today()
    except scraper.ScraperError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/api/scrape/league", tags=["scrape"])
def scrape_league(body: ScrapeLeagueBody, user: str = Depends(current_user)):
    try:
        return scraper.scrape_league_results(body.league.strip().lower())
    except scraper.ScraperError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/runs", tags=["scrape"])
def runs(user: str = Depends(current_user)):
    return [dict(r) for r in db.run_query(
        "SELECT * FROM scrape_runs ORDER BY id DESC LIMIT 20")]


# --------------------------- dados + previsão ---------------------------

@app.get("/api/leagues", tags=["data"])
def leagues(user: str = Depends(current_user)):
    return [dict(r) for r in db.run_query(
        "SELECT l.*, (SELECT COUNT(*) FROM matches m WHERE m.league_id=l.id) AS matches, "
        "(SELECT COUNT(*) FROM matches m WHERE m.league_id=l.id AND m.status='scheduled') AS scheduled "
        "FROM leagues l ORDER BY l.name")]


@app.get("/api/leagues/{league_id}/teams", tags=["data"])
def league_teams(league_id: int, user: str = Depends(current_user)):
    return [dict(r) for r in db.run_query(
        "SELECT t.id, t.name, "
        "(SELECT COUNT(*) FROM matches m WHERE (m.home_team_id=t.id OR m.away_team_id=t.id) "
        "  AND m.league_id=? AND m.status='played') AS games_played "
        "FROM teams t WHERE t.league_id=? ORDER BY t.name",
        (league_id, league_id))]


@app.post("/api/predict/fixture", tags=["prediction"])
def fixture_prediction(body: FixtureBody, user: str = Depends(current_user)):
    try:
        return predict_fixture(body.league_id, body.home_team_id, body.away_team_id)
    except IndexError:
        raise HTTPException(status_code=404, detail="Confronto não encontrado")


@app.get("/api/leagues/{league_id}/matches", tags=["data"])
def league_matches(league_id: int, user: str = Depends(current_user)):
    return [dict(r) for r in db.run_query(
        "SELECT m.id, m.match_date, m.kickoff, m.status, m.ht_home, m.ht_away, "
        "m.ft_home, m.ft_away, th.name AS home, ta.name AS away "
        "FROM matches m JOIN teams th ON th.id=m.home_team_id "
        "JOIN teams ta ON ta.id=m.away_team_id "
        "WHERE m.league_id=? ORDER BY m.match_date DESC, m.kickoff LIMIT 200",
        (league_id,))]


@app.get("/api/matches/{match_id}/prediction", tags=["prediction"])
def prediction(match_id: int, user: str = Depends(current_user)):
    try:
        return predict_match(match_id)
    except IndexError:
        raise HTTPException(status_code=404, detail="Partida não encontrada")


@app.get("/api/leagues/{league_id}/predictions", tags=["prediction"])
def league_predictions(league_id: int, user: str = Depends(current_user)):
    return predict_league_upcoming(league_id)


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