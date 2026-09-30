import uuid
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlparse

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from backend.app.api.v1.approvals import router as approvals_router
from backend.app.api.v1.auth import router as auth_router
from backend.app.api.v1.health import router as health_router
from backend.app.api.v1.metrics import router as metrics_router
from backend.app.api.v1.reminders import router as reminders_router
from backend.app.api.v1.settings import router as settings_router
from backend.app.api.v1.skills import router as skills_router
from backend.app.api.v1.websocket import router as ws_router
from backend.app.config import get_settings
from backend.app.core.exceptions import register_exception_handlers
from backend.app.core.logging import get_logger, request_id_ctx, setup_logging
from backend.app.db.session import get_session_maker
from backend.app.services.metrics_service import get_metrics_service
from backend.app.services.reminder_service import get_reminder_service

logger = get_logger("main")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    setup_logging(settings.LOG_LEVEL, settings.APP_ENV)
    from backend.app.core.logging import register_sensitive_token
    register_sensitive_token(settings.INITIAL_GEMINI_API_KEY)
    register_sensitive_token(settings.INITIAL_GROQ_API_KEY)
    register_sensitive_token(settings.INITIAL_OPENROUTER_API_KEY)
    register_sensitive_token(settings.SETUP_TOKEN)
    register_sensitive_token(settings.JWT_SECRET_KEY)
    settings.ensure_directories()
    logger.info(
        "NIKO backend initialized",
        version=settings.APP_VERSION,
        env=settings.APP_ENV,
        host=settings.HOST,
        port=settings.PORT,
    )
    metrics_service = get_metrics_service(session_factory=get_session_maker())
    await metrics_service.start_collector()

    reminder_service = get_reminder_service()
    await reminder_service.start_background_worker()

    # Discover models asynchronously at startup from each provider's list endpoint
    import asyncio

    from backend.app.llm.discovery import model_discovery
    from backend.app.repositories.settings_repository import SettingsRepository

    async def _startup_discovery() -> None:
        try:
            session_maker = get_session_maker()
            async with session_maker() as db:
                repo = SettingsRepository(db)
                keys = await repo.get_decrypted_provider_keys(settings.ENCRYPTION_KEY)
                if "gemini" not in keys and settings.INITIAL_GEMINI_API_KEY:
                    keys["gemini"] = settings.INITIAL_GEMINI_API_KEY
                if "groq" not in keys and settings.INITIAL_GROQ_API_KEY:
                    keys["groq"] = settings.INITIAL_GROQ_API_KEY
                if "openrouter" not in keys and settings.INITIAL_OPENROUTER_API_KEY:
                    keys["openrouter"] = settings.INITIAL_OPENROUTER_API_KEY
                await model_discovery.refresh_all(keys)
        except Exception as e:
            logger.warning("Startup model discovery encounter issue", error=str(e))

    asyncio.create_task(_startup_discovery())

    from backend.app.llm.deferred_queue import deferred_queue
    deferred_queue.start_worker()

    yield
    deferred_queue.stop_worker()
    await reminder_service.stop_background_worker()
    await metrics_service.stop_collector()
    logger.info("NIKO backend shutting down")



def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="NIKO - Personal AI Assistant API",
        version=settings.APP_VERSION,
        description="Private personal AI assistant backend running on localhost.",
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def request_id_middleware(
        request: Request, call_next: Callable[[Request], Any]
    ) -> Response:
        incoming_id = request.headers.get("X-Request-ID")
        req_id = incoming_id if incoming_id else f"req_{uuid.uuid4().hex[:16]}"
        token = request_id_ctx.set(req_id)
        try:
            response: Response = await call_next(request)
            response.headers["X-Request-ID"] = req_id
            return response
        finally:
            request_id_ctx.reset(token)

    @app.middleware("http")
    async def csrf_origin_middleware(
        request: Request, call_next: Callable[[Request], Any]
    ) -> Response:
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            origin = request.headers.get("origin")
            allowed_origins = [o.rstrip("/") for o in settings.CORS_ORIGINS]

            if origin:
                if origin.rstrip("/") not in allowed_origins:
                    logger.warning(
                        "Rejected mutating request with unauthorized origin",
                        origin=origin,
                        method=request.method,
                        path=request.url.path,
                    )
                    req_id = request_id_ctx.get()
                    return JSONResponse(
                        status_code=403,
                        content={
                            "error": {
                                "code": "INVALID_ORIGIN",
                                "message": f"Cross-site request blocked: Origin '{origin}' is not authorized.",
                                "request_id": req_id,
                                "details": {},
                            }
                        },
                    )
            else:
                referer = request.headers.get("referer")
                if referer:
                    parsed = urlparse(referer)
                    ref_origin = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
                    if ref_origin not in allowed_origins:
                        req_id = request_id_ctx.get()
                        return JSONResponse(
                            status_code=403,
                            content={
                                "error": {
                                    "code": "INVALID_ORIGIN",
                                    "message": f"Cross-site request blocked: Referer '{ref_origin}' is not authorized.",
                                    "request_id": req_id,
                                    "details": {},
                                }
                            },
                        )
                # Check for ambient cookie authentication without CSRF protection header
                has_cookie = "niko_access_token" in request.cookies or "niko_refresh_token" in request.cookies
                has_csrf_or_auth = (
                    "x-csrf-token" in request.headers
                    or "x-requested-with" in request.headers
                    or "authorization" in request.headers
                )
                if has_cookie and not has_csrf_or_auth:
                    req_id = request_id_ctx.get()
                    return JSONResponse(
                        status_code=403,
                        content={
                            "error": {
                                "code": "CSRF_TOKEN_REQUIRED",
                                "message": "Mutating requests authenticated via cookies must include an allowed Origin header or CSRF token header.",
                                "request_id": req_id,
                                "details": {},
                            }
                        },
                    )

        res: Response = await call_next(request)
        return res

    # 2. TrustedHostMiddleware: Prevents DNS rebinding and foreign Host headers
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.TRUSTED_HOSTS,
    )

    # 3. CORS Middleware: Restricts HTTP origin to local frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # 4. Global Exception Handlers
    register_exception_handlers(app)

    # 5. Route Inclusions
    app.include_router(health_router)
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(approvals_router, prefix="/api/v1")
    app.include_router(skills_router, prefix="/api/v1")
    app.include_router(metrics_router, prefix="/api/v1")
    app.include_router(settings_router, prefix="/api/v1")
    app.include_router(reminders_router, prefix="/api/v1")
    app.include_router(ws_router)

    return app


app = create_app()
