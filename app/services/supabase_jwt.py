"""Supabase JWT verification.

Verifies JWTs issued by Supabase Auth using either:
  - RS256 with JWKS (SUPABASE_JWKS_URL set) — preferred for production.
  - HS256 with the project JWT secret (SUPABASE_JWT_SECRET set) — simpler alternative.

SUPABASE_JWKS_URL is typically: {SUPABASE_URL}/auth/v1/.well-known/jwks.json

Both paths return the decoded payload dict on success, or None on failure.
The caller is responsible for extracting `sub` (Supabase user UUID) and any
other claims needed for authorization.
"""
from __future__ import annotations

import logging
from typing import Any

try:
    import jwt
    from jwt import PyJWKClient
    _JWT_AVAILABLE = True
except ImportError:
    _JWT_AVAILABLE = False

from app.config.settings import get_settings

logger = logging.getLogger(__name__)

_jwks_client: "PyJWKClient | None" = None


def _get_jwks_client() -> "PyJWKClient | None":
    global _jwks_client
    if not _JWT_AVAILABLE:
        return None
    settings = get_settings()
    jwks_url = (settings.SUPABASE_JWKS_URL or "").strip()
    if not jwks_url:
        # Auto-construct from SUPABASE_URL if available
        base = (settings.SUPABASE_URL or "").strip().rstrip("/")
        if base:
            jwks_url = f"{base}/auth/v1/.well-known/jwks.json"
        else:
            return None
    if _jwks_client is None:
        _jwks_client = PyJWKClient(jwks_url, cache_keys=True)
    return _jwks_client


def verify_supabase_token(token: str) -> dict[str, Any] | None:
    """Verify a Supabase-issued JWT and return the decoded payload, or None.

    Tries RS256 via JWKS first (preferred), then HS256 via the project
    JWT secret. Returns None if neither is configured or verification fails.
    """
    if not token or not _JWT_AVAILABLE:
        return None

    settings = get_settings()

    # RS256 via JWKS
    client = _get_jwks_client()
    if client:
        try:
            signing_key = client.get_signing_key_from_jwt(token)
            return jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience="authenticated",
            )
        except Exception as exc:
            logger.debug("Supabase JWKS verification failed: %s", exc)

    # HS256 via JWT secret
    secret = (settings.SUPABASE_JWT_SECRET or "").strip()
    if secret:
        try:
            return jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                audience="authenticated",
            )
        except Exception as exc:
            logger.debug("Supabase JWT secret verification failed: %s", exc)

    return None
