"""AP2WEB — FastAPI composition root (Fase 2.2).

Fonte única de dados: Sofascore. Rota handlers vivem em ``backend.app.api``;
este módulo só monta o app: lifespan, exception handlers, middleware, CORS,
routers e o SPA estático de produção.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path as FsPath

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config, db, security
from .api import state
from .api.admin import router as admin_router
from .api.auth import router as auth_router
from .api.backtest import router as backtest_router
from .api.data import router as data_router
from .api.evolution import router as evolution_router
from .api.health import router as health_router
from .api.jobs import router as jobs_router
from .api.learning import router as learning_router
from .api.market import router as market_router
from .api.middleware import SecurityHeadersMiddleware
from .api.prediction import router as prediction_router
from .api.risk import router as risk_router
from .api.sync import router as sync_router
from .api.v1 import V1EnvelopeMiddleware, register_v1_aliases
from .auth import bootstrap_admin

settings = config.settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("ap2web")


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
    worker_started = False
    try:
        db.init_db()
        if bootstrap_admin(settings.bootstrap_admin_username,
                           settings.bootstrap_admin_password):
            logger.info("bootstrap administrator configured")
        try:
            security.prune_audit_log()
        except Exception:
            logger.warning("audit prune failed at startup", exc_info=True)
    except Exception:
        state.started_ok = False
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
            state.started_ok = False
            logger.exception("jobs worker failed to start")
            raise
    else:
        logger.info("jobs worker disabled (AP2WEB_ENABLE_WORKER=false); "
                    "production should run `python -m backend.app.worker`")

    state.started_ok = True
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


app = FastAPI(title="AP2WEB", version=state.APP_VERSION, lifespan=_lifespan)


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
# Middleware: security headers + CORS (explicit origins only)
# ─────────────────────────────────────────────────────────────
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(V1EnvelopeMiddleware)
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
# Routers (tags preserved: auth, sofascore, jobs, data, prediction,
# learning, market, risk, evolution, backtest, admin, misc)
# ─────────────────────────────────────────────────────────────
_ROUTERS = (
    auth_router,
    sync_router,
    market_router,
    jobs_router,
    data_router,
    prediction_router,
    learning_router,
    risk_router,
    evolution_router,
    backtest_router,
    admin_router,
    health_router,
)
for _router in _ROUTERS:
    app.include_router(_router)


# --- /api/v1/* aliases with envelope (legacy /api/* unchanged) ---
# Must run after routers and BEFORE the SPA catch-all below.
_V1_PATHS = register_v1_aliases(app, _ROUTERS)
logger.info("registered %d v1 aliases", len(_V1_PATHS))


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
