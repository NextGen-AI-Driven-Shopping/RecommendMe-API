"""
FastAPI application factory.

Initialises the FastAPI instance, registers middleware, attaches
exception handlers, and mounts the versioned API router.
The lifespan context manager handles startup and shutdown events.
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.cache_cleaner import clear_all_caches
from app.routes.v1.router import router as v1_router
from app.core.exceptions import register_exception_handlers
from app.core.logger import get_logger
from app.core.middleware import register_middleware
from app.core.security import configure_cors

logger = get_logger(__name__)

# Always clean known cache artifacts before app initialization.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_cache_cleanup_result = clear_all_caches(str(_BACKEND_ROOT))
logger.info(
    "startup_cache_cleanup directories_deleted=%d files_deleted=%d errors=%d",
    _cache_cleanup_result["directories_deleted"],
    _cache_cleanup_result["files_deleted"],
    _cache_cleanup_result["errors"],
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and graceful shutdown."""
    logger.info("Starting up RecommendMe API...")
    # Request deduplication cache consumed by /v1/query handler.
    if not hasattr(app.state, "request_cache"):
        app.state.request_cache = {}  # request_id -> {timestamp, response}
    yield
    logger.info("Shutting down RecommendMe API...")


app = FastAPI(
    title="RecommendMe API",
    description="AI-powered product recommendation engine.",
    version="1.0.0",
    lifespan=lifespan,
)

configure_cors(app)
register_middleware(app)
register_exception_handlers(app)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if os.environ.get("APP_ENV", "development").lower() == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    return response

app.include_router(v1_router)


@app.get("/", include_in_schema=False)
async def root():
    """Welcome endpoint for RecommendMe API."""
    return JSONResponse(
        status_code=200,
        content={
            "message": "Welcome to RecommendMe API",
            "status": "✅ Server is running",
            "version": "1.0.0",
            "documentation": "/docs",
            "health_check": "/health",
        },
    )


@app.get("/health", include_in_schema=False)
async def liveness():
    """Lightweight liveness endpoint for platform health checks."""
    return JSONResponse(status_code=200, content={"status": "ok"})
