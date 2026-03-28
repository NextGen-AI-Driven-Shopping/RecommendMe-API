"""
Security configuration.

Covers:
  - CORS policy derived from Settings.CORS_ORIGINS.
  - Basic input sanitisation helper (whitespace and null-byte stripping).
  - Password hashing and verification using Bcrypt.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from passlib.context import CryptContext # <--- Add this

from app.core.config import get_settings

# Setup the hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto") # <--- Add this

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


def sanitize_input(text: str) -> str:
    """
    Strip leading/trailing whitespace and remove null bytes from user input.
    """
    return text.strip().replace("\x00", "")

# --- New Password Security Functions ---

def hash_password(password: str) -> str:
    """
    Scramble a plain-text password into a secure Bcrypt hash.
    Truncates to 72 bytes to prevent Bcrypt overflow errors.
    """
    # We slice the string to 72 characters before hashing
    safe_password = password[:72] 
    return pwd_context.hash(safe_password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check if a login password matches the stored hash."""
    # We must also slice here so it matches the hashed version
    safe_password = plain_password[:72]
    return pwd_context.verify(safe_password, hashed_password) 