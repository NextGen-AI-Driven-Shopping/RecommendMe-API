"""
Security configuration.

Covers:
  - CORS policy (using settings for production flexibility).
  - Basic input sanitization helper.
  - Rate limit rule constants.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings  # Import our central settings

def configure_cors(app: FastAPI) -> None:
    """Add CORS middleware with origins defined in config.py."""
    app.add_middleware(
        CORSMiddleware,
        # Use settings.CORS_ORIGINS instead of a hardcoded list
        allow_origins=settings.CORS_ORIGINS, 
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

def sanitize_input(text: str) -> str:
    """Strip leading/trailing whitespace and remove null bytes."""
    return text.strip().replace("\x00", "")