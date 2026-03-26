"""
Security configuration.

Covers:
  - CORS policy derived from Settings.CORS_ORIGINS.

Full injection detection (prompt injection, HTML, SQL) lives in
app/utils/validators.py and runs before any AI call is made.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.settings import get_settings


def configure_cors(app: FastAPI) -> None:
    """Add CORS middleware using the origins configured in Settings."""
    settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_origin_regex=settings.CORS_ORIGIN_REGEX,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
