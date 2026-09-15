"""AP2WEB — API FastAPI (Phase 2 security hardened).

Fonte única de dados: Sofascore.
Endpoints:
  POST /api/register            cadastro de usuário
  POST /api/login               login → access (cookie HttpOnly) + refresh (rotação)
  POST /api/logout              revoga sessão + limpa cookies
  POST /api/auth/refresh        rota refresh (rotação de refresh token)
  GET  /api/me                  identidade da sessão atual
  ... dados, previsões, jobs, learning, market, risk, evolution, backtest ...
"""
from __future__ import annotations

import logging
import re
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path as FsPath
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Path, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import MutableHeaders
from pydantic import BaseModel, ConfigDict, Field, field_validator

from . import config, db, security, sofascore_data
from .auth import (authenticate, create_user, current_user,
                   current_user_with_role, logout_session, refresh_session,
                   require_permission)
from .history import delete_prediction, list_predictions, save_prediction, stats
from .learning import calibration_status, model_status, motor_curve
from .prediction import predict_league_upcoming, predict_match, predict_fixture
from .ratelimit import rate_limit

settings = config.settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("ap2web")

# ─────────────────────────────────────────────────────────────
# Lifecycle (FastAPI lifespan — replaces deprecated on_event)
# ─────────────────────────────────────────────────────────────
# Startup outcome flag consulted by /api/ready. `None` = startup not finished
# yet; `True` = ready; `False` = startup failed.
_app_started_ok: bool | None = None


@asynccontextmanager
async def _lifespan(app):
    """Startup / shutdown for the AP2WEB API process.

    - initialize the database schema (job recovery is a separate operation);
    - optionally start the in-process jobs worker (dev opt-in only —
      production MUST run the separate worker process `backend.app.worker`);
    - expose startup failures: any exception here propagates, so uvicorn
      refuses to serve and TestClient raises on `with TestClient(...)`;
    - on shutdown, stop the worker and close database pools.
    """
    global _app_started_ok
    worker_started = False
    try:
        db.init_db()
        try:
            security.prune_audit_log()
        except Exception:
            logger.warning("audit prune failed at startup", exc_info=True)
    except Exception:
        _app_started_ok = False
        logger.exception("startup failed — refusing to serve")
        raise

    if settings.enable_worker:
        # Dev/opt-in only. Deduplication is enforced by jobs.start_worker()
        # (alive check) and by each Uvicorn worker running its own lifespan.
        try:
            from .jobs import start_worker

            start_worker()
            worker_started = True
            logger.info("jobs worker enabled in-process (AP2WEB_ENABLE_WORKER=true)")
        except Exception:
            _app_started_ok = False
            logger.exception("jobs worker failed to start")
            raise
    else:
        logger.info("jobs worker disabled (AP2WEB_ENABLE_WORKER=false); "
                    "production should run `python -m backend.app.worker`")

    _app_started_ok = True
    try:
        yield
    finally:
        if worker_started:
            try:
                from .jobs import stop_worker

                stop_worker()
            except Exception:
                logger.exception("error stopping worker")
        if db.MODE == "postgres":
            try:
                db._pool.close()
            except Exception:
                logger.exception("error closing db pool")


app = FastAPI(title="AP2WEB", version="0.2.0", lifespan=_lifespan)


# ─────────────────────────────────────────────────────────────
# Config helpers
# ─────────────────────────────────────────────────────────────
ACCESS_COOKIE = config.ACCESS_COOKIE
REFRESH_COOKIE = config.REFRESH_COOKIE
CSRF_COOKIE = config.CSRF_COOKIE


def _set_auth_cookies(resp, access: str, refresh: str, csrf: str) -> None:
    secure = settings.cookie_secure
    same = settings.cookie_samesite
    resp.set_cookie(
        ACCESS_COOKIE, access, httponly=True, secure=secure, samesite=same,
        max_age=settings.access_token_ttl_seconds, path="/")
    resp.set_cookie(
        REFRESH_COOKIE, refresh, httponly=True, secure=secure, samesite=same,
        max_age=settings.refresh_token_ttl_seconds, path="/")
    resp.set_cookie(
        CSRF_COOKIE, csrf, httponly=False, secure=secure, samesite=same,
        max_age=settings.refresh_token_ttl_seconds, path="/")


def _clear_auth_cookies(resp) -> None:
    resp.delete_cookie(ACCESS_COOKIE, path="/")
    resp.delete_cookie(REFRESH_COOKIE, path="/")
    resp.delete_cookie(CSRF_COOKIE, path="/")


def _public_auth_response(data: dict) -> dict:
    """Return session metadata without exposing bearer or refresh secrets."""
    return {
        "username": data["username"],
        "role": data["role"],
        "session_id": data.get("session_id"),
        "expires_in": data.get("expires_in"),
    }


def csrf_protect(request: Request) -> None:
    """CSRF dependency for state-changing endpoints (see security.csrf_protect)."""
    security.csrf_protect(request)


def _audit(user: dict | None, action: str, request: Request | None = None, *,
           success: bool = True, error_code: str | None = None,
           resource_type: str | None = None, resource_id: str | int | None = None,
           metadata: dict | None = None) -> None:
    security.audit_event(
        request, action=action, success=success, error_code=error_code,
        username=(user or {}).get("username"), role=(user or {}).get("role"),
        resource_type=resource_type, resource_id=resource_id, metadata=metadata)


# ─────────────────────────────────────────────────────────────
# Error handling (safe format, no internals leaked)
# ─────────────────────────────────────────────────────────────
@app.exception_handler(HTTPException)
async def _http_exception_handler(request: Request, exc: HTTPException):
    detail = str(exc.detail)
    body = security.safe_error_body(exc.status_code, detail, request)
    headers = dict(exc.headers or {})
    return JSONResponse(status_code=exc.status_code, content=body, headers=headers)


@app.exception_handler(RequestValidationError)
async def _validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    if errors:
        first = errors[0]
        loc = ".".join(str(x) for x in first.get("loc", []) if x != "body")
        type_ = first.get("type", "")
        msg = f"Payload inválido ({loc}): {type_}" if loc else "Payload inválido"
    else:
        msg = "Payload inválido"
    body = security.safe_error_body(400, msg, request)
    return JSONResponse(status_code=400, content=body)


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    rid = getattr(request.state, "request_id", None)
    logger.exception("unhandled error rid=%s path=%s exc=%s", rid, request.url.path, type(exc).__name__)
    body = security.safe_error_body(500, "Erro interno", request)
    return JSONResponse(status_code=500, content=body)


# ─────────────────────────────────────────────────────────────
# Security headers + request-id middleware
# ─────────────────────────────────────────────────────────────
_CSP_BASE = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "img-src 'self' data:; "
    "font-src https://fonts.gstatic.com; "
    "connect-src 'self' https://fonts.googleapis.com https://fonts.gstatic.com; "
    "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
)
if settings.production:
    _CSP = _CSP_BASE + "; upgrade-insecure-requests"
else:
    _CSP = _CSP_BASE

_SENSITIVE_PREFIXES = ("/api/login", "/api/logout", "/api/auth/", "/api/me")


class SecurityHeadersMiddleware:
    """Pure ASGI security middleware; avoids BaseHTTPMiddleware buffering."""

    def __init__(self, application):
        self.application = application

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.application(scope, receive, send)
            return

        request = Request(scope, receive)
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        request.state.request_id = rid
        start = time.time()
        content_length = request.headers.get("Content-Length")
        if content_length:
            try:
                if int(content_length) > settings.max_body_bytes:
                    response = JSONResponse(
                        status_code=413,
                        content=security.safe_error_body(
                            413, "Payload demasiado grande", request),
                        headers={"X-Request-ID": rid},
                    )
                    await response(scope, receive, send)
                    return
            except ValueError:
                pass

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
                headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
                headers["Content-Security-Policy"] = _CSP
                if settings.production:
                    headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
                headers["X-Request-ID"] = rid
                path = request.url.path
                is_api = path.startswith("/api/") or path == "/api"
                if is_api:
                    authed = bool(request.headers.get("Authorization")) or bool(
                        request.cookies.get(ACCESS_COOKIE))
                    sensitive = path.startswith(_SENSITIVE_PREFIXES) or request.method in (
                        "POST", "PUT", "PATCH", "DELETE")
                    if sensitive or authed:
                        headers["Cache-Control"] = "no-store"
                dur = (time.time() - start) * 1000
                if is_api and (dur > 500 or path in ("/api/sofascore/sync", "/api/learning/calibrate")):
                    logger.info("req rid=%s %s %s %s %.1fms", rid, request.method, path,
                                message["status"], dur)
            await send(message)

        await self.application(scope, receive, send_with_headers)


app.add_middleware(SecurityHeadersMiddleware)


# ─────────────────────────────────────────────────────────────
# CORS — explicit origins only
# ─────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
    expose_headers=settings.cors_expose_headers,
    max_age=settings.cors_max_age,
)


# ─────────────────────────────────────────────────────────────
# Request models (validated)
# ─────────────────────────────────────────────────────────────
class RegisterBody(BaseModel):
    username: str = Field(min_length=config.settings.username_min,
                          max_length=config.settings.username_max,
                          pattern=r"^[A-Za-z0-9._-]+$")
    password: str = Field(min_length=config.settings.password_min,
                          max_length=config.settings.password_max)


class LoginBody(BaseModel):
    username: str = Field(min_length=1, max_length=config.settings.username_max)
    password: str = Field(min_length=1, max_length=config.settings.password_max)


class RefreshBody(BaseModel):
    refresh_token: str | None = Field(default=None, max_length=200)


class FixtureBody(BaseModel):
    league_id: int = Field(gt=0)
    home_team_id: int = Field(gt=0)
    away_team_id: int = Field(gt=0)


class RoleChangeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "operator", "admin"]


ALIASES_OK = ConfigDict(extra="ignore")


class PredictionBody(BaseModel):
    model_config = ALIASES_OK

    league_id: int = Field(gt=0)
    match_id: int = Field(gt=0)
    home_team_id: int = Field(gt=0)
    away_team_id: int = Field(gt=0)
    home_name: str = Field(min_length=1, max_length=120)
    away_name: str = Field(min_length=1, max_length=120)
    match_date: str | None = Field(default=None, max_length=40)
    pick_type: str = Field(min_length=1, max_length=30, pattern=r"^[A-Za-z0-9_-]+$")
    pick_value: str = Field(min_length=1, max_length=50)
    pick_label: str = Field(default="", max_length=120)
    prob: float
    odd: float = Field(gt=0, le=10000)
    payload: dict = Field(default_factory=dict)

    @field_validator("match_date")
    @classmethod
    def _valid_date(cls, v):
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        import datetime as _dt
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%SZ"):
            try:
                _dt.datetime.strptime(v[:23], fmt if len(v) <= 23 else "%Y-%m-%dT%H:%M:%S")
                return v
            except ValueError:
                continue
        raise ValueError("data inválida")

    @field_validator("prob")
    @classmethod
    def _finite_prob(cls, v):
        import math
        if v is None or not math.isfinite(v) or v < 0 or v > 1:
            raise ValueError("probabilidade deve estar entre 0 e 1")
        return v

    @field_validator("odd")
    @classmethod
    def _finite_odd(cls, v):
        import math
        if v is not None and not math.isfinite(v):
            raise ValueError("odd inválida")
        return v


    @field_validator("pick_value")
    @classmethod
    def _valid_pick_value(cls, value, info):
        pick_type = info.data.get("pick_type")
        valid = (
            (pick_type == "1X2" and value in {"1", "X", "2"})
            or (pick_type == "GOLS" and re.fullmatch(
                r"(?:over|under)_(?:0|[1-9][0-9]*)\.5", value))
            or (pick_type == "BTTS" and value in {"sim", "nao"})
        )
        if not valid:
            raise ValueError("jogada não suportada")
        return value

    @field_validator("pick_type")
    @classmethod
    def _valid_pick_type(cls, value):
        if value not in {"1X2", "GOLS", "BTTS"}:
            raise ValueError("tipo de jogada não suportado")
        return value


class OddsQuoteBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str = Field(min_length=1, max_length=120)
    captured_at: str = Field(min_length=20, max_length=40)
    odds: dict[str, float]
    source_event_id: str | None = Field(default=None, max_length=120)


class RiskConfigBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kelly_fraction: float = Field(default=0.25, ge=0, le=1)
    bankroll: float = Field(default=1000.0, gt=0)
    max_stake_pct: float = Field(default=0.05, ge=0, le=1)
    max_exposure_pct: float = Field(default=0.15, ge=0, le=1)
    max_daily_pct: float = Field(default=0.25, ge=0, le=1)
    min_edge: float = Field(default=0.02, ge=0, le=1)
    min_prob: float = Field(default=0.30, ge=0, le=1)
    max_odds: float = Field(default=10.0, gt=1)

    @field_validator("*")
    @classmethod
    def _finite_floats(cls, v):
        import math
        if isinstance(v, float) and not math.isfinite(v):
            raise ValueError("valores devem ser finitos")
        return v


def _clamp_limit(limit: int, hi: int = 100) -> int:
    try:
        v = int(limit)
    except (TypeError, ValueError):
        return 20
    return max(1, min(v, hi))


# ─────────────────────────────────────────────────────────────
# Auth endpoints
# ─────────────────────────────────────────────────────────────
@app.post("/api/register", tags=["auth"])
def register(body: RegisterBody, request: Request, _: None = Depends(rate_limit("register"))):
    create_user(body.username, body.password)
    security.audit_event(request, action="register", success=True, username=body.username,
                         role="user")
    return {"ok": True, "message": "Usuário criado"}


@app.post("/api/login", tags=["auth"])
def login(body: LoginBody, request: Request, _: None = Depends(rate_limit("login"))):
    data = authenticate(body.username, body.password, request)
    resp = JSONResponse(content=_public_auth_response(data))
    _set_auth_cookies(resp, data["token"], data["refresh_token"], data["csrf_token"])
    return resp


@app.post("/api/logout", tags=["auth"])
def logout(request: Request, _: None = Depends(csrf_protect)):
    logout_session(request)
    resp = JSONResponse(content={"ok": True})
    _clear_auth_cookies(resp)
    return resp


@app.post("/api/auth/refresh", tags=["auth"])
def auth_refresh(body: RefreshBody, request: Request,
                 _: None = Depends(csrf_protect),
                 __: None = Depends(rate_limit("refresh"))):
    refresh_raw = body.refresh_token or request.cookies.get(REFRESH_COOKIE)
    if not refresh_raw:
        raise HTTPException(status_code=401, detail="Sessão inválida")
    data = refresh_session(refresh_raw, request)
    resp = JSONResponse(content=_public_auth_response(data))
    _set_auth_cookies(resp, data["token"], data["refresh_token"], data["csrf_token"])
    return resp


@app.get("/api/me", tags=["auth"])
def me(user: dict = Depends(current_user_with_role)):
    return {"username": user["username"], "role": user["role"],
            "session_id": user.get("session_id"), "user_id": user.get("user_id")}


# --------------------------- dados (Sofascore) ---------------------------

@app.post("/api/sofascore/sync", tags=["sofascore"])
def sofascore_sync(request: Request, user: dict = Depends(require_permission("sync:data")),
                   _: None = Depends(csrf_protect), __: None = Depends(rate_limit("sync"))):
    """Sincroniza todas as ligas — cria job persistente. Requer operator/admin."""
    rid = getattr(request.state, "request_id", None)
    _audit(user, "sofascore.sync_all", request, resource_type="job")
    logger.info("sync_all job requested by %s rid=%s", user["username"], rid)
    from .jobs import create_job
    try:
        uid = _user_id(user["username"])
    except Exception:
        uid = 0
    try:
        job = create_job("sync_all", requested_by=uid or 0, parameters={})
        return {"ok": True, "job": job, "job_id": job["id"]}
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.post("/api/sofascore/sync/league/{league_id}", tags=["sofascore"])
def sofascore_sync_league(league_id: int = Path(gt=0), request: Request = None,
                          user: dict = Depends(require_permission("sync:league")),
                          _: None = Depends(csrf_protect), __: None = Depends(rate_limit("sync"))):
    """Sincroniza uma liga — job persistente. Requer operator/admin."""
    _audit(user, "sofascore.sync_league", request, resource_type="league", resource_id=league_id)
    logger.info("sync_league %s by %s", league_id, user["username"])
    if not db.run_query("SELECT id FROM leagues WHERE id=?", (league_id,)):
        raise HTTPException(status_code=404, detail="Liga não encontrada")
    from .jobs import create_job
    try:
        uid = _user_id(user["username"])
    except Exception:
        uid = 0
    try:
        job = create_job("sync_league", requested_by=uid, league_id=league_id,
                         parameters={"league_id": league_id})
        return {"ok": True, "job": job, "job_id": job["id"]}
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.post("/api/odds/sync", tags=["market"])
def odds_sync(sport_key: str, request: Request,
              region: str = "eu", user: dict = Depends(require_permission("sync:data")),
              _: None = Depends(csrf_protect), __: None = Depends(rate_limit("sync"))):
    """Enfileira ingestão auditável de odds 1X2 da The Odds API."""
    from .jobs import create_job
    _audit(user, "odds.sync", request, resource_type="job")
    try:
        job = create_job("sync_odds", requested_by=_user_id(user["username"]),
                         parameters={"sport_key": sport_key, "region": region})
        return {"ok": True, "job": job, "job_id": job["id"]}
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@app.get("/api/sofascore/status", tags=["sofascore"])
def sofascore_status(user: dict = Depends(current_user_with_role)):
    """Return synchronization status from the durable jobs table."""
    from .jobs import list_jobs

    recent = list_jobs(limit=10, job_type="sync_all")
    recent.extend(list_jobs(limit=10, job_type="sync_league"))
    recent.sort(key=lambda job: job.get("id", 0), reverse=True)
    active = [job for job in recent if job.get("status") in ("pending", "running")]
    return {
        "running": bool(active),
        "jobs": recent[:10],
        "active_job": active[0] if active else None,
    }


# --------------------------- jobs ---------------------------

@app.get("/api/jobs/{job_id}", tags=["jobs"])
def get_job_endpoint(job_id: int = Path(gt=0), user: dict = Depends(current_user_with_role)):
    from .jobs import get_job
    j = get_job(job_id)
    if not j:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    if user.get("role") != "admin" and j.get("requested_by") != _user_id(user["username"]):
        raise HTTPException(status_code=403, detail="Permissão negada")
    return j


@app.get("/api/jobs", tags=["jobs"])
def list_jobs_endpoint(limit: int = 20, job_type: str | None = None,
                       user: dict = Depends(current_user_with_role)):
    from .jobs import list_jobs
    limit = _clamp_limit(limit, 100)
    user_id = None if user.get("role") == "admin" else _user_id(user["username"])
    return list_jobs(user_id=user_id, limit=limit, job_type=job_type)


@app.post("/api/jobs/{job_id}/cancel", tags=["jobs"])
def cancel_job_endpoint(job_id: int = Path(gt=0), request: Request = None,
                        user: dict = Depends(require_permission("job:cancel")),
                        _: None = Depends(csrf_protect),
                        __: None = Depends(rate_limit("job_cancel"))):
    from .jobs import cancel_job
    try:
        j = cancel_job(job_id, {"username": user["username"], "role": user["role"],
                                "user_id": _user_id(user["username"])})
        _audit(user, "jobs.cancel", request, resource_type="job", resource_id=job_id,
               metadata={"status": j.get("status")})
        return j
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permissão negada")
    except LookupError:
        raise HTTPException(status_code=404, detail="Job não encontrado")


@app.get("/api/sofascore/data", tags=["sofascore"])
def sofascore_data_endpoint(league_id: int | None = None, next_round: int = 1,
                            user: str = Depends(current_user)):
    return sofascore_data.dataset(league_id, next_round=bool(next_round))


@app.get("/api/leagues", tags=["data"])
def leagues(user: str = Depends(current_user)):
    return sofascore_data.leagues()


@app.get("/api/leagues/{league_id}/teams", tags=["data"])
def league_teams(league_id: int = Path(gt=0), user: str = Depends(current_user)):
    return [dict(r) for r in db.run_query(
        "SELECT t.id, t.name, "
        "(SELECT COUNT(*) FROM matches m WHERE (m.home_team_id=t.id OR m.away_team_id=t.id) "
        "  AND m.league_id=? AND m.status='played') AS games_played "
        "FROM teams t WHERE t.league_id=? ORDER BY t.name",
        (league_id, league_id))]


@app.get("/api/leagues/{league_id}/matches", tags=["data"])
def league_matches(league_id: int = Path(gt=0), user: str = Depends(current_user)):
    return [dict(r) for r in db.run_query(
        "SELECT m.id, m.kickoff_datetime, m.round, m.status, m.score_home, m.score_away, "
        "m.xg_home, m.xg_away, th.name AS home, ta.name AS away "
        "FROM matches m JOIN teams th ON th.id=m.home_team_id "
        "JOIN teams ta ON ta.id=m.away_team_id "
        "WHERE m.league_id=? ORDER BY m.kickoff_datetime DESC, m.id LIMIT 200",
        (league_id,))]


@app.get("/api/matches/{match_id}/prediction", tags=["prediction"])
def prediction(match_id: int = Path(gt=0), user: str = Depends(current_user),
               as_of_timestamp: str | None = None):
    try:
        return predict_match(match_id, as_of_timestamp=as_of_timestamp)
    except IndexError:
        raise HTTPException(status_code=404, detail="Partida não encontrada")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/predict/fixture", tags=["prediction"])
def fixture_prediction(body: FixtureBody, user: str = Depends(current_user),
                       _: None = Depends(csrf_protect),
                       __: None = Depends(rate_limit("fixture")),
                       as_of_timestamp: str | None = None):
    try:
        return predict_fixture(body.league_id, body.home_team_id, body.away_team_id,
                               as_of_timestamp=as_of_timestamp)
    except IndexError:
        raise HTTPException(status_code=404, detail="Confronto não encontrado")


@app.get("/api/leagues/{league_id}/predictions", tags=["prediction"])
def league_predictions(league_id: int = Path(gt=0), user: str = Depends(current_user),
                       as_of_timestamp: str | None = None):
    return predict_league_upcoming(league_id, as_of_timestamp=as_of_timestamp)


# --------------------------- comparação Poisson vs Bayesian ---------------------------

@app.get("/api/matches/{match_id}/compare", tags=["prediction"])
def compare_prediction(match_id: int = Path(gt=0), user: str = Depends(current_user)):
    poisson_result = predict_match(match_id, use_bayesian=False)
    bayesian_result = predict_match(match_id, use_bayesian=True)

    poisson = {
        "lambdas": poisson_result.get("lambdas"),
        "probs": poisson_result.get("probs"),
        "top_scores": poisson_result.get("top_scores"),
        "inputs": poisson_result.get("inputs"),
        "model": poisson_result.get("model"),
    }
    bayesian = bayesian_result.get("bayesian")

    return {
        "match": poisson_result.get("match"),
        "poisson": poisson,
        "bayesian": bayesian,
        "comparison": _bayesian_comparison(poisson, bayesian),
    }


def _bayesian_comparison(poisson: dict, bayesian: dict) -> dict:
    if not bayesian:
        return {"status": "bayesian_unavailable"}

    p1x2 = poisson.get("probs", {}).get("1x2", {})
    b1x2 = bayesian.get("probs", {}).get("1x2", {})

    diff = {
        "prob_1_diff": round(b1x2.get("1", 0) - p1x2.get("1", 0), 4),
        "prob_X_diff": round(b1x2.get("X", 0) - p1x2.get("X", 0), 4),
        "prob_2_diff": round(b1x2.get("2", 0) - p1x2.get("2", 0), 4),
    }

    p_lambda_home = poisson.get("lambdas", {}).get("home", 0)
    p_lambda_away = poisson.get("lambdas", {}).get("away", 0)
    b_lambda_home = bayesian.get("lambdas", {}).get("home", 0)
    b_lambda_away = bayesian.get("lambdas", {}).get("away", 0)

    return {
        **diff,
        "lambda_home_poisson": p_lambda_home,
        "lambda_away_poisson": p_lambda_away,
        "lambda_home_bayesian": b_lambda_home,
        "lambda_away_bayesian": b_lambda_away,
        "lambda_home_diff": round(b_lambda_home - p_lambda_home, 3),
        "lambda_away_diff": round(b_lambda_away - p_lambda_away, 3),
        "bayesian_weight_home": bayesian.get("home_bayesian_weight", 0),
        "bayesian_weight_away": bayesian.get("away_bayesian_weight", 0),
    }


@app.get("/api/bayesian/league/{league_id}", tags=["prediction"])
def bayesian_league_summary(league_id: int = Path(gt=0), user: str = Depends(current_user)):
    from .prediction import _get_bayesian_engine
    engine = _get_bayesian_engine(league_id)
    return engine.summary()


# --------------------------- histórico de previsões ---------------------------

def _user_id(username: str) -> int:
    row = db.run_query("SELECT id FROM users WHERE username=?", (username,))
    if not row:
        raise HTTPException(status_code=401, detail="Usuário não encontrado")
    return row[0]["id"]


@app.post("/api/predictions", tags=["prediction"])
def create_prediction(body: PredictionBody, user: str = Depends(current_user),
                       _: None = Depends(csrf_protect),
                       __: None = Depends(rate_limit("prediction"))):
    try:
        return save_prediction(_user_id(user), body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/predictions", tags=["prediction"])
def get_predictions(user: str = Depends(current_user)):
    uid = _user_id(user)
    return {"stats": stats(uid), "items": list_predictions(uid)}


@app.delete("/api/predictions/{prediction_id}", tags=["prediction"])
def remove_prediction(prediction_id: int = Path(gt=0), user: str = Depends(current_user),
                      _: None = Depends(csrf_protect)):
    deleted = delete_prediction(_user_id(user), prediction_id)
    return {"ok": deleted is not None and deleted is not False}


# --------------------------- aprendizado / calibração ---------------------------

@app.post("/api/learning/calibrate", tags=["learning"])
def learning_calibrate(request: Request, user: dict = Depends(require_permission("run:calibration")),
                       _: None = Depends(csrf_protect), __: None = Depends(rate_limit("calibrate"))):
    _audit(user, "learning.calibrate_all", request, resource_type="job")
    logger.info("calibrate_all job by %s", user["username"])
    from .jobs import create_job
    try:
        uid = _user_id(user["username"])
    except Exception:
        uid = 0
    try:
        job = create_job("calibrate_all", requested_by=uid, parameters={})
        return {"ok": True, "job": job, "job_id": job["id"]}
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.post("/api/learning/calibrate/{league_id}", tags=["learning"])
def learning_calibrate_league(league_id: int = Path(gt=0), request: Request = None,
                              user: dict = Depends(require_permission("run:calibration")),
                              _: None = Depends(csrf_protect),
                              __: None = Depends(rate_limit("calibrate"))):
    _audit(user, "learning.calibrate_league", request, resource_type="league", resource_id=league_id)
    from .jobs import create_job
    cnt = db.run_query("SELECT COUNT(*) c FROM matches WHERE league_id=? AND status='played'", (league_id,))
    if cnt and cnt[0]["c"] < 5:
        raise HTTPException(status_code=400, detail="Liga sem dados suficientes")
    try:
        uid = _user_id(user["username"])
    except Exception:
        uid = 0
    try:
        job = create_job("calibrate_league", requested_by=uid, league_id=league_id,
                         parameters={"league_id": league_id})
        return {"ok": True, "job": job, "job_id": job["id"]}
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.get("/api/learning/calibrate/status", tags=["learning"])
def learning_calibrate_status(user: str = Depends(current_user)):
    return calibration_status()


@app.get("/api/learning/status", tags=["learning"])
def learning_status(user: str = Depends(current_user)):
    return model_status()


@app.get("/api/learning/curve", tags=["learning"])
def learning_curve(user: str = Depends(current_user)):
    return motor_curve()


@app.get("/api/learning/backtest/{league_id}", tags=["learning"])
def learning_backtest(league_id: int = Path(gt=0), user: str = Depends(current_user)):
    from .backtest_engine import run_single_league_backtest
    return run_single_league_backtest(league_id)


@app.get("/api/learning/xgb/{league_id}", tags=["learning"])
def learning_xgb_comparison(league_id: int = Path(gt=0), user: str = Depends(current_user)):
    """BASE.md §26-27: comparação honesta XGBoost vs Poisson (walk-forward temporal)."""
    from .xgb_engine import compare_models
    return compare_models(league_id)


@app.get("/api/market/{match_id}", tags=["market"])
def market_match(match_id: int = Path(gt=0), as_of: str | None = None,
                  user: str = Depends(current_user)):
    from .market import market_for_match
    try:
        return market_for_match(match_id, as_of)
    except IndexError:
        raise HTTPException(status_code=404, detail="Partida não encontrada")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/market/{match_id}/quotes", status_code=201, tags=["market"])
def market_quote(match_id: int, body: OddsQuoteBody,
                 user: dict = Depends(require_permission("sync:data"))):
    from .odds_store import save_1x2_quote
    try:
        save_1x2_quote(match_id, body.provider, body.captured_at, body.odds, body.source_event_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "match_id": match_id, "market_type": "1x2"}


@app.get("/api/market/league/{league_id}", tags=["market"])
def market_league(league_id: int = Path(gt=0), limit: int = 20,
                  as_of: str | None = None,
                  user: str = Depends(current_user)):
    from .market import market_league
    return market_league(league_id, _clamp_limit(limit, 100), as_of)


# --------------------------- FASE 11 — Risk Engine ---------------------------

@app.get("/api/risk/{match_id}", tags=["risk"])
def risk_match(match_id: int = Path(gt=0), as_of: str | None = None,
               kelly_fraction: float = 0.25,
               bankroll: float = 1000.0,
               user: str = Depends(current_user)):
    from .risk import risk_for_match, RiskConfig
    cfg = RiskConfig(kelly_fraction=min(max(kelly_fraction, 0.0), 1.0),
                     bankroll=max(bankroll, 1.0))
    try:
        return risk_for_match(match_id, cfg, as_of)
    except IndexError:
        raise HTTPException(status_code=404, detail="Partida não encontrada")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/risk/league/{league_id}", tags=["risk"])
def risk_league_endpoint(league_id: int = Path(gt=0), limit: int = 20,
                         as_of: str | None = None,
                         kelly_fraction: float = 0.25,
                         bankroll: float = 1000.0,
                         user: str = Depends(current_user)):
    from .risk import risk_league, RiskConfig
    cfg = RiskConfig(kelly_fraction=min(max(kelly_fraction, 0.0), 1.0),
                     bankroll=max(bankroll, 1.0))
    return risk_league(league_id, _clamp_limit(limit, 100), cfg, as_of)


@app.post("/api/risk/portfolio", tags=["risk"])
def risk_portfolio(matches: list[int], kelly_fraction: float = 0.25,
                   bankroll: float = 1000.0,
                   user: str = Depends(current_user),
                   _: None = Depends(csrf_protect),
                   __: None = Depends(rate_limit("prediction"))):
    from .risk import risk_for_match, portfolio_risk, RiskConfig
    clean = [int(m) for m in (matches or []) if int(m) > 0][:100]
    cfg = RiskConfig(kelly_fraction=min(max(kelly_fraction, 0.0), 1.0),
                     bankroll=max(bankroll, 1.0))
    matches_risk = [risk_for_match(mid, cfg) for mid in clean]
    return portfolio_risk(matches_risk, cfg)


@app.get("/api/evolution/snapshot", tags=["evolution"])
def evolution_snapshot(user: str = Depends(current_user)):
    from .evolution_tracker import (_snapshot, _load_baseline, _compare,
                                     _append_history, _history_count,
                                     _evolution_pct, _load_history,
                                     _start_measurement_execution,
                                     _finish_measurement_execution)
    execution = _start_measurement_execution(skip_regression=True, source="endpoint")
    try:
        current = _snapshot(skip_regression=True)
        baseline = _load_baseline()
        current["api_health"] = True
        current["regression_suite"] = baseline.get("regression_suite") if baseline else None
        changes = _compare(current, baseline) if baseline else []
        history = _load_history(limit=10**9)
        evolution = _evolution_pct(current, history) if history else {}

        if current.get("leagues"):
            league_ids = [int(lid) for lid in current["leagues"].keys()]
            placeholders = ",".join("?" for _ in league_ids)
            league_names = db.run_query(
                f"SELECT id, name FROM leagues WHERE id IN ({placeholders})",
                tuple(league_ids))
            name_map = {str(r["id"]): r["name"] for r in league_names}
            for lid, m in current["leagues"].items():
                m["league_name"] = name_map.get(lid, f"Liga {lid}")

        _append_history(current)
    except Exception as error:
        _finish_measurement_execution(execution, "failed", error=str(error)[:2000])
        raise
    history_size = _history_count()
    _finish_measurement_execution(execution, "completed", snapshot=current, results={
        "changes": changes,
        "evolution": evolution,
        "history_size": history_size,
    })
    return {
        "current": current,
        "baseline": baseline,
        "changes": changes,
        "evolution": evolution,
        "stable": len(changes) == 0,
        "history_size": history_size,
        "env": "dev" if settings.env != "production" else "deploy",
    }


@app.get("/api/evolution/history", tags=["evolution"])
def evolution_history(limit: int = 50, user: str = Depends(current_user)):
    from .evolution_tracker import _load_history, _trend_series
    history = _load_history(_clamp_limit(limit, 500))
    return {
        "count": len(history),
        "history": history,
        "series": _trend_series(history),
    }


# --------------------------- Backtest Engine (jobs-backed) ---------------------------

def _create_backtest_job(user: dict, mode: str, interval_hours: float | None = None,
                         league_ids: list[int] | None = None) -> dict:
    from .jobs import create_job

    params: dict = {"mode": mode}
    if interval_hours is not None:
        params["interval_hours"] = interval_hours
    if league_ids:
        params["league_ids"] = league_ids
    uid = _user_id(user["username"])
    try:
        return create_job("backtest", requested_by=uid, parameters=params)
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))


def _active_backtest_jobs() -> list[dict]:
    from .jobs import list_jobs

    return [j for j in list_jobs(limit=50, job_type="backtest")
            if j.get("status") in ("pending", "running")]


@app.post("/api/backtest/start", tags=["backtest"])
def backtest_start(request: Request,
                   user: dict = Depends(require_permission("run:backtest")),
                   _: None = Depends(csrf_protect),
                   __: None = Depends(rate_limit("backtest")),
                   interval_hours: float = 6.0):
    """Inicia um ciclo de backtest como JOB persistente (sem thread daemon)."""
    interval_hours = min(max(interval_hours, 0.5), 24 * 30)
    job = _create_backtest_job(user, "start", interval_hours=interval_hours)
    _audit(user, "backtest.start", request, resource_type="job", resource_id=job["id"],
           metadata={"interval_hours": interval_hours})
    return {"ok": True, "job": job, "job_id": job["id"]}


@app.post("/api/backtest/stop", tags=["backtest"])
def backtest_stop(request: Request,
                  user: dict = Depends(require_permission("run:backtest")),
                  _: None = Depends(csrf_protect),
                  __: None = Depends(rate_limit("backtest"))):
    """Cancela jobs de backtest ativos (persistido na tabela de jobs)."""
    from .jobs import cancel_job

    cancelled = []
    for j in _active_backtest_jobs():
        j = cancel_job(j["id"], {"username": user["username"], "role": user["role"],
                                 "user_id": user.get("user_id")})
        cancelled.append(j["id"])
    _audit(user, "backtest.stop", request, resource_type="job",
           metadata={"cancelled_ids": cancelled})
    return {"ok": True, "cancelled": cancelled}


@app.get("/api/backtest/status", tags=["backtest"])
def backtest_status(user: str = Depends(current_user)):
    """Status de backtest — leitura do jobs table (read-only compat)."""
    from .jobs import list_jobs

    active = _active_backtest_jobs()
    recent = list_jobs(limit=10, job_type="backtest")
    return {
        "running": bool(active),
        "active_jobs": active,
        "jobs": recent,
    }


@app.post("/api/backtest/run", tags=["backtest"])
def backtest_run(request: Request,
                 league_ids: list[int] | None = None,
                 user: dict = Depends(require_permission("run:backtest")),
                 _: None = Depends(csrf_protect),
                 __: None = Depends(rate_limit("backtest"))):
    """Executa um ciclo de backtest em ligas específicas como JOB persistente."""
    cleaned = None
    if league_ids:
        cleaned = [int(x) for x in league_ids if int(x) > 0][:200]
    job = _create_backtest_job(user, "run", league_ids=cleaned)
    _audit(user, "backtest.run", request, resource_type="job", resource_id=job["id"],
           metadata={"leagues": cleaned})
    return {"ok": True, "job": job, "job_id": job["id"]}


@app.get("/api/backtest/cv/{league_id}", tags=["backtest"])
def backtest_temporal_cv(league_id: int = Path(gt=0), n_folds: int = 5,
                          user: str = Depends(current_user)):
    n_folds = _clamp_limit(n_folds, 20)
    from .backtest_engine import run_temporal_cv
    return run_temporal_cv(league_id, n_folds)


@app.get("/api/backtest/history", tags=["backtest"])
def backtest_history(limit: int = 20, user: str = Depends(current_user)):
    from .backtest_engine import get_loop
    limit = _clamp_limit(limit, 200)
    loop = get_loop()
    history = loop.get_history(limit)
    return {"history": history, "total": len(loop.get_history(1000))}


@app.get("/api/backtest/meta", tags=["backtest"])
def backtest_meta(user: str = Depends(current_user)):
    from .backtest_engine import get_loop
    loop = get_loop()
    return {
        "total_records": len(loop.meta.history),
        "recent": loop.meta.history[-50:],
    }


@app.get("/api/backtest/summary", tags=["backtest"])
def backtest_summary(user: str = Depends(current_user)):
    from .backtest_engine import get_loop
    return get_loop().get_summary()


# --------------------------- admin ---------------------------

@app.post("/api/admin/users/{user_id}/role", tags=["admin"])
def admin_set_role(user_id: int = Path(gt=0), body: RoleChangeBody | None = None,
                   request: Request = None,  # FastAPI injects; kept for audit
                   admin: dict = Depends(require_permission("manage:users")),
                   _: None = Depends(csrf_protect),
                   __: None = Depends(rate_limit("admin"))):
    if body is None:
        raise HTTPException(status_code=400, detail="Payload vazio — informe o novo papel")
    if int(admin.get("user_id") or 0) == user_id:
        raise HTTPException(status_code=400, detail="Não é possível alterar o próprio papel")
    rows = db.run_query("SELECT id, username FROM users WHERE id=?", (user_id,))
    if not rows:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    db.run_exec("UPDATE users SET role=? WHERE id=?", (body.role, user_id))
    _audit(admin, "admin.role_change", request, success=True,
           resource_type="user", resource_id=user_id,
           metadata={"target": rows[0]["username"], "new_role": body.role})
    return {"ok": True, "user_id": user_id, "username": rows[0]["username"], "role": body.role}


@app.delete("/api/admin/users/{user_id}", tags=["admin"])
def admin_delete_user(user_id: int = Path(gt=0), request: Request = None,
                      admin: dict = Depends(require_permission("manage:users")),
                      _: None = Depends(csrf_protect),
                      __: None = Depends(rate_limit("admin"))):
    if int(admin.get("user_id") or 0) == user_id:
        raise HTTPException(status_code=400, detail="Não é possível excluir a si mesmo")
    rows = db.run_query("SELECT id, username FROM users WHERE id=?", (user_id,))
    if not rows:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    db.run_exec("UPDATE users SET is_active=0 WHERE id=?", (user_id,))
    # revoke all of the user's sessions
    db.run_exec("UPDATE auth_sessions SET revoked_at=datetime('now'), revoked_reason='user_deleted' "
                "WHERE user_id=? AND revoked_at IS NULL", (user_id,))
    _audit(admin, "admin.user_delete", request, success=True,
           resource_type="user", resource_id=user_id, metadata={"target": rows[0]["username"]})
    return {"ok": True, "deleted_user_id": user_id, "username": rows[0]["username"]}


@app.get("/api/admin/audit", tags=["admin"])
def admin_audit(limit: int = 100, action: str | None = None,
                admin: dict = Depends(require_permission("manage:system"))):
    items = security.admin_audit_records(_clamp_limit(limit, 500), action)
    return {"items": items, "count": len(items),
            "retention_days": settings.audit_retention_days}


# --------------------------- health / readiness ---------------------------

def _db_reachable() -> bool:
    try:
        db.run_query("SELECT 1 AS ok", ())
        return True
    except Exception:
        return False


def _schema_ready() -> bool:
    """True when the schema is initialized and the baseline migration applied."""
    try:
        rows = db.run_query(
            "SELECT version FROM schema_migrations WHERE version=?", ("20260909_baseline",))
        users = db.run_query("SELECT COUNT(*) AS c FROM users", ())
        return bool(rows) and bool(users)
    except Exception:
        return False


def _worker_expected() -> bool:
    return bool(config.settings.require_worker or config.settings.enable_worker)


def _worker_healthy() -> bool:
    """A required worker must have a recent durable heartbeat."""
    try:
        from .jobs import worker_healthy
        return worker_healthy(config.settings.worker_heartbeat_seconds * 3)
    except Exception:
        return False


def _external_data_source_status() -> dict:
    """Report durable successful-sync freshness without making an upstream call."""
    max_age = settings.source_sync_max_age_seconds
    try:
        rows = db.run_query("SELECT last_sync FROM leagues ORDER BY last_sync DESC LIMIT 1")
        if not rows:
            return {"status": "not_configured", "last_sync": None,
                    "age_seconds": None, "max_age_seconds": max_age}
        last_sync = rows[0]["last_sync"]
        if not last_sync:
            return {"status": "degraded", "last_sync": None,
                    "age_seconds": None, "max_age_seconds": max_age}
        parsed = datetime.fromisoformat(str(last_sync).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        age_seconds = max(0, int((datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds()))
        return {"status": "ok" if age_seconds <= max_age else "degraded",
                "last_sync": last_sync, "age_seconds": age_seconds,
                "max_age_seconds": max_age}
    except Exception:
        return {"status": "error", "last_sync": None,
                "age_seconds": None, "max_age_seconds": max_age}


@app.get("/api/health", tags=["misc"])
def health():
    """Liveness only — the process is up and the app is responding.

    Deliberately does NOT touch the database or any external service so the
    liveness probe never thrashes during a DB outage.
    """
    return {"ok": True, "app": "AP2WEB", "version": app.version}


@app.get("/api/ready", tags=["misc"])
def ready():
    """Readiness — the service can accept production traffic.

    Verifies startup completed, the database is reachable, the schema and the
    baseline migration are applied, the configuration is valid, and (when
    worker mode is enabled) the worker store is healthy. Returns HTTP 503 with
    a safe body when any of those checks fail.
    """
    ok_startup = _app_started_ok is True
    ok_db = _db_reachable()
    ok_schema = _schema_ready() if ok_db else False
    ok_config = True  # invalid config already aborted startup
    ok_worker = not _worker_expected() or _worker_healthy()
    ready_all = ok_startup and ok_db and ok_schema and ok_config and ok_worker
    body = {
        "ok": ready_all,
        "ready": ready_all,
        "checks": {
            "startup": ok_startup,
            "database": ok_db,
            "schema": ok_schema,
            "config": ok_config,
            "worker": ok_worker,
        },
    }
    return JSONResponse(status_code=200 if ready_all else 503, content=body)


@app.get("/api/health/dependencies", tags=["misc"])
def health_dependencies():
    """Safe dependency status. No secrets, stack traces, SQL, or paths leaked."""
    db_ok = _db_reachable()

    external = _external_data_source_status()

    return {
        "database": {
            "status": "ok" if db_ok else "error",
            "mode": db.MODE,
        },
        "job_worker": {
            "status": "enabled" if _worker_expected() else "disabled",
            "healthy": _worker_healthy() if _worker_expected() else None,
        },
        "audit": {
            "status": "ok" if security.audit_persistence_healthy() else "degraded",
            "persistence_failures": security.audit_failure_count(),
        },
        "external_data_source": external,
        "rate_limit_storage": {
            "backend": config.settings.rate_limit_storage,
            "healthy": True,
        },
    }


# --- frontend estático (produção tudo-em-um) — registrado POR ÚLTIMO ---
_FRONTEND_DIST = FsPath(__file__).resolve().parents[2] / "frontend" / "dist"
if _FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIST / "assets"), name="assets")

    @app.get("/")
    def _index():
        return FileResponse(_FRONTEND_DIST / "index.html")

    @app.get("/{full_path:path}")
    def _spa(full_path: str):
        candidate = (_FRONTEND_DIST / full_path).resolve()
        if not candidate.is_relative_to(_FRONTEND_DIST.resolve()):
            raise HTTPException(status_code=404, detail="Arquivo não encontrado")
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_FRONTEND_DIST / "index.html")
