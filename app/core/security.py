"""
Security configuration.

Covers:
  - CORS policy derived from Settings.CORS_ORIGINS.
  - Basic input sanitisation helper (whitespace and null-byte stripping).

Full injection detection (prompt injection, HTML, SQL) lives in
app/utils/validators.py and runs before any AI call is made.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings


def configure_cors(app: FastAPI) -> None:
    """Add CORS middleware using the origins configured in Settings."""
    settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def sanitize_input(text: str) -> str:
    """
    Strip leading/trailing whitespace and remove null bytes from user input.

    This is the first-pass sanitisation step.  Full prompt-injection and
    HTML-injection validation is handled by app/utils/validators.py.
    """
    return text.strip().replace("\x00", "")
