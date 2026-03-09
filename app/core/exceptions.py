"""
Custom exception classes and HTTP error handlers.

Define domain-specific exceptions here.  Register all handlers with
the FastAPI application by calling register_exception_handlers().
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class VagueQueryError(Exception):
    """Raised when a user query is classified as too vague to process."""

    def __init__(self, message: str = "Query is too vague. Please provide more context."):
        self.message = message
        super().__init__(self.message)


class ExternalServiceError(Exception):
    """Raised when a required external service (OpenAI, SerpAPI, Redis) is unavailable."""

    def __init__(self, service: str, detail: str = ""):
        self.service = service
        self.detail = detail
        super().__init__(f"{service} error: {detail}")


class RateLimitExceededError(Exception):
    """Raised when a client exceeds the configured request rate limit."""

    pass


# ── HTTP error handlers ────────────────────────────────────────────────────────

async def _vague_query_handler(request: Request, exc: VagueQueryError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"error": exc.message})


async def _external_service_handler(request: Request, exc: ExternalServiceError) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"error": f"External service unavailable: {exc.service}"},
    )


async def _rate_limit_handler(request: Request, exc: RateLimitExceededError) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"error": "Rate limit exceeded. Please try again later."},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all custom exception handlers to the FastAPI application."""
    app.add_exception_handler(VagueQueryError, _vague_query_handler)
    app.add_exception_handler(ExternalServiceError, _external_service_handler)
    app.add_exception_handler(RateLimitExceededError, _rate_limit_handler)
