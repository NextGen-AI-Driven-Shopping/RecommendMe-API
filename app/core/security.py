"""
Security configuration.

Covers:
  - CORS policy derived from Settings.CORS_ORIGINS.
  - Production safety guard for the lenient localhost regex.
  - Method/header allowlists narrowed to only what the API uses.

Full injection detection (prompt injection, HTML, SQL) lives in
app/utils/validators.py and runs before any AI call is made.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.settings import get_settings


def configure_cors(app: FastAPI) -> None:
    """Add CORS middleware using the origins configured in Settings.

    The localhost-only regex fallback is intentionally disabled in
    production so a misconfigured deployment cannot accept requests
    from arbitrary local origins exposed via tunnels. Methods and
    headers are pinned to the explicit set the API consumes.
    """
    settings = get_settings()
    is_production = settings.APP_ENV.lower() == "production"
    origin_regex = None if is_production else settings.CORS_ORIGIN_REGEX

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_origin_regex=origin_regex,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Correlation-ID", "X-Request-ID"],
    )
