"""
SkyView Smart Agriculture — FastAPI Application
Entry point. Thin orchestrator — logic lives in routers/agents.
"""

import os
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from skyview.data.db import init_db
from skyview.data.v3.db import enabled as v3_enabled
from skyview.utils.config import get_settings
from skyview.utils.logger import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)

settings = get_settings()

app = FastAPI(
    title="SkyView Smart Agriculture API",
    version="3.1.0",
    description="Multi-agent IoT + AI agricultural platform",
)


class PerformanceAndCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()
        response: Response = await call_next(request)
        process_time = time.perf_counter() - start_time
        response.headers["X-Process-Time-Ms"] = f"{process_time * 1000:.2f}"

        if request.method == "GET" and response.status_code == 200:
            path = request.url.path
            if (
                request.headers.get("Authorization")
                or request.headers.get("X-Assistant-Session")
                or path.startswith(
                    (
                        "/api/profile",
                        "/api/sensors",
                        "/api/assistant",
                        "/api/marketplace",
                        "/api/recent-alerts",
                        "/api/trends",
                        "/api/advisor",
                        "/api/disease",
                    )
                )
            ):
                response.headers["Cache-Control"] = "no-store"
                response.headers["Vary"] = "Authorization, X-Assistant-Session"
                return response
            if any(
                p in path
                for p in [
                    "/api/mandi",
                    "/api/marketplace/farmers",
                    "/api/marketplace/loops",
                    "/api/marketplace/directory",
                    "/api/trends",
                    "/api/schemes",
                ]
            ):
                if "cache-control" not in response.headers:
                    response.headers["Cache-Control"] = (
                        "public, max-age=300, stale-while-revalidate=86400"
                    )
            elif (
                any(p in path for p in ["/api/sensor/readings", "/api/weather"])
                and "cache-control" not in response.headers
            ):
                response.headers["Cache-Control"] = (
                    "public, max-age=15, stale-while-revalidate=60"
                )
        return response


app.add_middleware(PerformanceAndCacheMiddleware)


class SelectiveGZipMiddleware:
    """Do not buffer incremental assistant events behind a compression threshold."""

    def __init__(self, app, minimum_size=1000):
        self.app = app
        self.compressed = GZipMiddleware(app, minimum_size=minimum_size)

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        if (
            scope["type"] == "http"
            and path.startswith("/api/assistant/sessions/")
            and path.endswith("/run")
        ):
            await self.app(scope, receive, send)
        else:
            await self.compressed(scope, receive, send)


app.add_middleware(SelectiveGZipMiddleware, minimum_size=1000)


safe_cors_origins = [o for o in settings.CORS_ORIGINS if o != "*"]
if not safe_cors_origins:
    safe_cors_origins = ["http://localhost:5173", "http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=safe_cors_origins,
    allow_origin_regex=None if os.getenv("K_SERVICE") else r"^(https://[a-zA-Z0-9-]+\.vercel\.app|http://(?:localhost|127\.0\.0\.1):\d+)$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "Origin",
        "X-Requested-With",
        "X-Assistant-Session",
        "If-Match",
        "Last-Event-ID",
    ],
)


@app.on_event("startup")
async def on_startup():
    from skyview.data.v3 import db as canonical

    if os.getenv("K_SERVICE") and canonical.mode() != "v3_live":
        raise RuntimeError("Cloud Run requires the authenticated v3_live data lane")
    if os.getenv("K_SERVICE") and not all(
        os.getenv(name)
        for name in (
            "ASSISTANT_S3_BUCKET",
            "AWS_ENDPOINT_URL_S3",
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_REGION",
        )
    ):
        raise RuntimeError("Cloud Run requires durable object storage for farm files")
    if canonical.enabled():
        if os.getenv("K_SERVICE"):
            if not os.getenv("CORS_ORIGINS") or any(not origin.startswith("https://") for origin in settings.CORS_ORIGINS):
                raise RuntimeError("Cloud Run requires explicit HTTPS CORS origins")
            if os.getenv("V3_BACKGROUND_WORKER", "false").lower() == "true":
                raise RuntimeError("Cloud Run requires request-driven and scheduled workers")
        if os.getenv("K_SERVICE") and settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
            required = ("WHATSAPP_TASK_QUEUE", "WHATSAPP_TASK_SERVICE_ACCOUNT", "SKYVIEW_PUBLIC_URL")
            if any(not os.getenv(name) for name in required):
                raise RuntimeError("Cloud Run WhatsApp requires a task queue, service identity, and public HTTPS URL")
        if not canonical.health():
            raise RuntimeError("V3 schema unavailable; refusing legacy fallback")
        from skyview.assistant.catalog import sync_runtime_catalog
        from skyview.data.v3.worker import start_background_worker

        sync_runtime_catalog()
        await start_background_worker()
        logger.info("SkyView unified v3 API started; mode=%s", canonical.mode())
        return
    logger.info("=" * 55)
    logger.info("🌾 SkyView Backend v2.0 starting…")
    logger.info("=" * 55)
    logger.info("Groq keys configured: %d", len(settings.GROQ_API_KEYS))

    try:
        init_db()
    except SQLAlchemyError as exc:
        logger.warning("DB init warning (%s)", type(exc).__name__)

    from sqlalchemy import text

    from skyview.data.db import get_session

    try:
        db = get_session()
        db.execute(
            text("""
            CREATE TABLE IF NOT EXISTS users (
                phone VARCHAR(20) PRIMARY KEY,
                name VARCHAR(100),
                land_size_acres FLOAT,
                location VARCHAR(200),
                crops TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        )
        db.commit()

        column_ddls = [
            text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION"
            ),
            text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION"
            ),
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS state VARCHAR(100)"),
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS district VARCHAR(100)"),
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS excess_resources TEXT"),
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS required_resources TEXT"),
            text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS whatsapp_number VARCHAR(20)"
            ),
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS saved_otp VARCHAR(10)"),
        ]
        for ddl_stmt in column_ddls:
            try:
                db.execute(ddl_stmt)
                db.commit()
            except SQLAlchemyError as col_exc:
                db.rollback()
                logger.debug("Column migration note (%s)", type(col_exc).__name__)

        db.close()
    except SQLAlchemyError as exc:
        logger.warning("Users table check (%s)", type(exc).__name__)


def _register(module_path: str, attr: str = "router", prefix: str = ""):
    try:
        import importlib

        mod = importlib.import_module(module_path)
        router = getattr(mod, attr)
        app.include_router(router, prefix=prefix)
        logger.info("[OK] Registered: %s", module_path)
    except (ImportError, AttributeError, RuntimeError) as exc:
        logger.warning(
            "[WARN] Could not register %s (%s)", module_path, type(exc).__name__
        )


if v3_enabled():
    from skyview.api.assistant_routes import router as assistant_router
    from skyview.api.disease_routes import router as disease_router
    from skyview.api.v3_companion_routes import router as companion_router
    from skyview.api.v3_compat_routes import router as compatibility_router
    from skyview.api.v3_exchange_ai_routes import router as exchange_ai_router
    from skyview.api.v3_exchange_routes import router as exchange_router
    from skyview.api.v3_explorer_routes import router as explorer_router
    from skyview.api.v3_farm_workflow_routes import router as workflow_router
    from skyview.api.v3_onboarding_routes import router as onboarding_router
    from skyview.api.v3_support_folder_routes import router as support_folder_router
    from skyview.api.v3_routes import router as v3_router
    from skyview.api.v3_voice_routes import router as voice_router
    from skyview.api.v3_whatsapp_routes import router as whatsapp_router

    app.include_router(v3_router)
    app.include_router(support_folder_router)
    app.include_router(compatibility_router)
    app.include_router(explorer_router)
    app.include_router(voice_router)
    app.include_router(whatsapp_router)
    app.include_router(companion_router)
    app.include_router(exchange_router)
    app.include_router(exchange_ai_router)
    app.include_router(onboarding_router)
    from skyview.api.v3_shared_work_routes import router as shared_work_router

    app.include_router(shared_work_router)
    app.include_router(workflow_router)
    app.include_router(assistant_router)
    app.include_router(disease_router)
else:
    _register("skyview.api.core_routes")

    _register("skyview.api.sensor_routes")

    _register("skyview.api.auth_routes")

    _register("skyview.api.chat_routes")
    _register("skyview.api.assistant_routes")

    _register("skyview.api.fpga_routes")

    _register("skyview.api.advisor_routes")

    _register("skyview.api.mandi_routes")

    _register("skyview.api.webhook_routes")

    _register("skyview.api.voice_routes")

    _register("skyview.api.voice_agent")

    _register("skyview.api.profile_routes")

    _register("skyview.api.marketplace_routes")

    _register("skyview.api.disease_routes")

_register("skyview.admin.admin_routes")


@app.on_event("shutdown")
async def shutdown():
    if v3_enabled():
        from skyview.data.v3.worker import stop_background_worker

        await stop_background_worker()
