"""
Security configuration.

Covers:
  - CORS policy (allowed origins, methods, headers).
  - Basic input sanitization helper.
  - Rate limit rule constants used by the rate limiter.

Full injection detection lives in app/utils/validators.py.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

ALLOWED_ORIGINS: list[str] = [
    "http://localhost:3000",
    "http://localhost:8000",
]


def configure_cors(app: FastAPI) -> None:
    """Add CORS middleware with the configured allowed origins."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def sanitize_input(text: str) -> str:
    """
    Strip leading/trailing whitespace and remove null bytes.

    Full prompt-injection and HTML-injection checks are handled
    in app/utils/validators.py before this function is called.
    """
    return text.strip().replace("\x00", "")
