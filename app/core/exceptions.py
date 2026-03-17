"""
Custom exception classes and global exception handler registration.

All domain-specific errors inherit from BaseAPIException, which itself
inherits from FastAPI's HTTPException so they are automatically
serialised to JSON error responses via the standard exception handler.

Call register_exception_handlers(app) in the application factory to
attach handlers for unhandled exceptions and custom domain errors.
"""

import traceback

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.core.logger import get_logger

logger = get_logger(__name__)


# --------------------------------------------------------------------------- #
# Custom exception hierarchy
# --------------------------------------------------------------------------- #

class BaseAPIException(HTTPException):
    """Base class for all custom API exceptions."""

    def __init__(
        self,
        detail: str = None,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    ):
        super().__init__(
            status_code=status_code,
            detail=detail or self.__class__.__doc__,
        )


class AIServiceException(BaseAPIException):
    """Raised when OpenAI or Ollama fails to respond."""

    def __init__(self, detail: str = "AI service is currently unavailable."):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
        )


class RateLimitException(BaseAPIException):
    """Raised when a client exceeds the configured request rate limit."""

    def __init__(self, detail: str = "Rate limit exceeded. Please try again later."):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
        )


class ValidationException(BaseAPIException):
    """Raised when user input fails validation (e.g. injection detected)."""

    def __init__(self, detail: str = "Invalid input."):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        )


# --------------------------------------------------------------------------- #
# Exception handlers
# --------------------------------------------------------------------------- #

async def _http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Serialise any HTTPException (including our custom subclasses) to JSON."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all handler for unexpected runtime errors.

    Logs the full traceback at ERROR level so the issue is visible in
    structured logs without leaking implementation details to the caller.
    """
    logger.error(
        f"Unhandled exception on {request.method} {request.url.path}: "
        f"{exc!r}\n{traceback.format_exc()}"
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred."},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all exception handlers to a FastAPI application instance."""
    app.add_exception_handler(HTTPException, _http_exception_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)