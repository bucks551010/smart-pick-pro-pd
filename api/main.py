"""api/main.py – FastAPI application entry point for Smart Pick Pro."""
import datetime
import os
from contextlib import asynccontextmanager
from utils.logger import get_logger

_logger = get_logger(__name__)

try:
    from fastapi import FastAPI
    from fastapi.middleware.gzip import GZipMiddleware
    from fastapi.middleware.cors import CORSMiddleware
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False
    _logger.warning("fastapi not installed; api/main.py will not function")

if _FASTAPI_AVAILABLE:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Warm caches on startup; release resources on shutdown."""
        _logger.info("Smart Pick Pro API starting up — warming caches")
        try:
            from utils.cache import cache_set
            cache_set("startup_ts", datetime.datetime.utcnow().isoformat(), tier="static")
        except Exception as exc:
            _logger.debug("Cache warm failed: %s", exc)
        yield
        _logger.info("Smart Pick Pro API shutting down")

    app = FastAPI(
        title="Smart Pick Pro API",
        description="Prediction and stats API for Smart Pick Pro",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Middleware
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    _allowed_origins = [
        o.strip()
        for o in os.environ.get("CORS_ALLOWED_ORIGINS", os.environ.get("APP_URL", "http://localhost:8501")).split(",")
        if o.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    try:
        from api.middleware import TimingMiddleware
        app.add_middleware(TimingMiddleware)
    except Exception as exc:
        _logger.debug("TimingMiddleware not loaded: %s", exc)

    # Routers
    try:
        from api.routes.health import router as health_router
        app.include_router(health_router)
    except Exception as exc:
        _logger.warning("health router failed to load: %s", exc)

    try:
        from api.routes.predictions import router as predictions_router
        app.include_router(predictions_router)
    except Exception as exc:
        _logger.warning("predictions router failed to load: %s", exc)

    try:
        from api.routes.players import router as players_router
        app.include_router(players_router)
    except Exception as exc:
        _logger.warning("players router failed to load: %s", exc)

    try:
        from api.routes.session import router as session_router
        app.include_router(session_router)
    except Exception as exc:
        _logger.warning("session router failed to load: %s", exc)

    try:
        from api.routes.auth import router as auth_router
        app.include_router(auth_router)
    except Exception as exc:
        _logger.warning("auth router failed to load: %s", exc)

    try:
        from api.routes.notifications import router as notifications_router
        app.include_router(notifications_router)
    except Exception as exc:
        _logger.warning("notifications router failed to load: %s", exc)

    try:
        from api.routes.seo import router as seo_router
        app.include_router(seo_router)
    except Exception as exc:
        _logger.warning("seo router failed to load: %s", exc)

    # ── /healthz — zero-cost liveness probe ──────────────────────
    # Intentionally inline (not a router) so it is ALWAYS registered
    # regardless of which optional routers fail to load.
    # Load balancers, ACA probes, and the Nginx upstream all hit this.
    # It performs NO database I/O and NO external calls; it must respond
    # in under 2 s even under full load.
    @app.get("/healthz", include_in_schema=False)
    async def healthz():
        return {"status": "ok"}

else:
    app = None
