"""
Request middleware.

Provides:
  - Correlation ID injection (X-Correlation-ID header echoed on responses).
  - Per-request timing.
  - Structured request/response logging with sensitive data scrubbed.
  - Security response headers (X-Frame-Options, CSP-lite, HSTS in prod).

Register all middleware by calling register_middleware(app).
"""

import os
import time
import uuid
from urllib.parse import parse_qsl, urlencode, urlparse

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.logger import get_logger

logger = get_logger(__name__)

# Query-param keys whose values must never appear in logs.
_SENSITIVE_PARAMS = {
    "token",
    "reset_token",
    "password",
    "api_key",
    "secret",
    "key",
    "authorization",
}


def _scrub_url(url: str) -> str:
    """Remove sensitive query-param values from a URL string before logging."""
    try:
        parsed = urlparse(url)
        params = parse_qsl(parsed.query, keep_blank_values=True)
        scrubbed = [
            (k, "***" if k.lower() in _SENSITIVE_PARAMS else v)
            for k, v in params
        ]
        safe_query = urlencode(scrubbed)
        return parsed._replace(query=safe_query).geturl()
    except Exception:
        return url


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
                    "path": _scrub_url(str(request.url)),
                    "duration_ms": duration_ms,
                    "correlation_id": correlation_id,
                },
                exc_info=True,
            )
            raise

        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        log_data = {
            "method": request.method,
            "path": _scrub_url(str(request.url)),
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


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Apply baseline browser-side security headers to every response.

    HSTS is only emitted when APP_ENV=production so local development
    over plain HTTP keeps working.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-XSS-Protection", "1; mode=block")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=()",
        )
        if os.environ.get("APP_ENV", "development").lower() == "production":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains; preload",
            )
        return response


def register_middleware(app: FastAPI) -> None:
    """Register all middleware used by the API application."""
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
