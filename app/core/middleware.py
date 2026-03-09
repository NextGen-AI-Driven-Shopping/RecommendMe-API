"""
Request middleware.

Provides:
  - Correlation ID injection (X-Correlation-ID header echoed on responses).
  - Per-request timing.
  - Structured request/response logging.

Register all middleware by calling register_middleware(app).
"""

import time
import uuid

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.logger import get_logger

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every incoming request with its duration and correlation ID."""

    async def dispatch(self, request: Request, call_next) -> Response:
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        start = time.perf_counter()

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info(
            f"{request.method} {request.url.path} "
            f"status={response.status_code} duration={duration_ms}ms "
            f"correlation_id={correlation_id}"
        )
        response.headers["X-Correlation-ID"] = correlation_id
        return response


def register_middleware(app: FastAPI) -> None:
    """Attach all middleware to the FastAPI application."""
    app.add_middleware(RequestLoggingMiddleware)
