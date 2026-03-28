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
    async def dispatch(self, request: Request, call_next) -> Response:
        correlation_id = (
            request.headers.get("X-Correlation-ID")
            or str(uuid.uuid4())
        )

        request.state.correlation_id = correlation_id
        start = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)

            logger.error(
                "request_failed",
                extra={
                    "method": request.method,
                    "path": str(request.url),
                    "duration_ms": duration_ms,
                    "correlation_id": correlation_id,
                },
                exc_info=True,
            )
            raise

        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        log_data = {
            "method": request.method,
            "path": str(request.url),
            "status": response.status_code,
            "duration_ms": duration_ms,
            "correlation_id": correlation_id,
            "client_ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        }

        if response.status_code >= 500:
            logger.error("request_completed", extra=log_data)
        elif response.status_code >= 400:
            logger.warning("request_completed", extra=log_data)
        else:
            logger.info("request_completed", extra=log_data)

        response.headers["X-Correlation-ID"] = correlation_id
        return response


def register_middleware(app: FastAPI) -> None:
    """Register all middleware used by the API application."""
    app.add_middleware(RequestLoggingMiddleware)