import uuid
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from backend.app.api.v1.auth import router as auth_router
from backend.app.api.v1.health import router as health_router
from backend.app.api.v1.websocket import router as ws_router
from backend.app.config import get_settings
from backend.app.core.exceptions import register_exception_handlers
from backend.app.core.logging import get_logger, request_id_ctx, setup_logging

logger = get_logger("main")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    setup_logging(settings.LOG_LEVEL, settings.APP_ENV)
    settings.ensure_directories()
    logger.info(
        "NIKO backend initialized",
        version=settings.APP_VERSION,
        env=settings.APP_ENV,
        host=settings.HOST,
        port=settings.PORT,
    )
    yield
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
    app.include_router(ws_router)

    return app


app = create_app()
