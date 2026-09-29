from typing import Any
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.app.core.logging import get_logger, request_id_ctx

logger = get_logger("exceptions")


class APIErrorDetails(BaseModel):
    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error explanation")
    request_id: str = Field(..., description="Unique request tracing ID")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional structured error metadata")


class APIErrorResponse(BaseModel):
    error: APIErrorDetails


class NIKOException(Exception):
    """Base exception for all domain errors in NIKO."""

    status_code: int = 500
    code: str = "INTERNAL_SERVER_ERROR"

    def __init__(
        self,
        message: str,
        code: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        self.details = details or {}


class AuthenticationError(NIKOException):
    status_code = 401
    code = "AUTHENTICATION_FAILED"


class PermissionDeniedError(NIKOException):
    status_code = 403
    code = "PERMISSION_DENIED"


class NotFoundError(NIKOException):
    status_code = 404
    code = "RESOURCE_NOT_FOUND"


class ConflictError(NIKOException):
    status_code = 409
    code = "RESOURCE_CONFLICT"


class SetupForbiddenError(NIKOException):
    status_code = 403
    code = "SETUP_ALREADY_COMPLETED"


class InvalidSetupTokenError(NIKOException):
    status_code = 401
    code = "INVALID_SETUP_TOKEN"


class RateLimitExceededError(NIKOException):
    status_code = 429
    code = "RATE_LIMIT_EXCEEDED"


class ApprovalRequiredError(NIKOException):
    status_code = 403
    code = "APPROVAL_REQUIRED"


class InvalidOriginError(NIKOException):
    status_code = 403
    code = "INVALID_ORIGIN"


class ValidationFailedError(NIKOException):
    status_code = 422
    code = "VALIDATION_FAILED"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(NIKOException)
    async def niko_exception_handler(_: Request, exc: NIKOException) -> JSONResponse:
        req_id = request_id_ctx.get()
        logger.warning(
            "Domain exception encountered",
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            details=exc.details,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=APIErrorResponse(
                error=APIErrorDetails(
                    code=exc.code,
                    message=exc.message,
                    request_id=req_id,
                    details=exc.details,
                )
            ).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        req_id = request_id_ctx.get()
        logger.info("Request validation failed", errors=exc.errors())
        return JSONResponse(
            status_code=422,
            content=APIErrorResponse(
                error=APIErrorDetails(
                    code="VALIDATION_FAILED",
                    message="Invalid request body or query parameters.",
                    request_id=req_id,
                    details={"validation_errors": exc.errors()},
                )
            ).model_dump(),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        req_id = request_id_ctx.get()
        code_map = {
            400: "BAD_REQUEST",
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            429: "TOO_MANY_REQUESTS",
        }
        code = code_map.get(exc.status_code, "HTTP_ERROR")
        return JSONResponse(
            status_code=exc.status_code,
            content=APIErrorResponse(
                error=APIErrorDetails(
                    code=code,
                    message=str(exc.detail),
                    request_id=req_id,
                    details={},
                )
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
        req_id = request_id_ctx.get()
        logger.error("Unhandled server exception", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=APIErrorResponse(
                error=APIErrorDetails(
                    code="INTERNAL_SERVER_ERROR",
                    message="An unexpected internal error occurred.",
                    request_id=req_id,
                    details={},
                )
            ).model_dump(),
        )
