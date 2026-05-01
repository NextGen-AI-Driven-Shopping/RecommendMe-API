"""Authentication dependencies and helpers.

Verification order:
  1. Supabase JWT (RS256 via JWKS or HS256 via JWT secret) — preferred.
  2. Legacy custom HMAC token — transitional fallback until all clients
     migrate to Supabase Auth.

Ownership enforcement (session_id / user_id comparisons) is unchanged
regardless of which token type was accepted.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.models.responses import AuthUser
from app.services.auth_csv import CsvAuthService
from app.services.auth_token import is_token_revoked, verify_auth_token
from app.services.supabase_jwt import verify_supabase_token

_bearer_scheme = HTTPBearer(auto_error=False)
_auth_service = CsvAuthService()


def _user_context_from_supabase(payload: dict, token: str) -> dict:
    """Build a user-context dict from a verified Supabase JWT payload.

    Tries to enrich with local CSV data when a matching record exists
    (same UUID). If not found, constructs a minimal AuthUser from JWT
    claims — enough for ownership enforcement via user_id comparison.
    """
    user_id = payload.get("sub", "")
    local_user = _auth_service.get_user_by_id(user_id)
    if local_user:
        return {"user": local_user, "session_id": payload.get("sid"), "token": token}

    email = payload.get("email") or ""
    minimal_user = AuthUser(
        user_id=user_id,
        username=email.split("@")[0] if email else user_id[:8],
        first_name="",
        last_name="",
        email=email or None,
        phone=None,
        created_at="",
    )
    return {"user": minimal_user, "session_id": payload.get("sid"), "token": token}


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme)):
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token.")

    token = credentials.credentials

    # Supabase JWT (preferred path)
    supabase_payload = verify_supabase_token(token)
    if supabase_payload:
        if is_token_revoked(token):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session has been revoked.")
        if not supabase_payload.get("sub"):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token: missing subject.")
        return _user_context_from_supabase(supabase_payload, token)

    # Legacy custom token (transitional fallback)
    if is_token_revoked(token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session has been revoked.")

    legacy_payload = verify_auth_token(token)
    if not legacy_payload or not legacy_payload.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token.")

    user = _auth_service.get_user_by_id(legacy_payload["sub"])
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")

    return {"user": user, "session_id": legacy_payload.get("sid"), "token": token}


def get_optional_user(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme)):
    """Return the current user if a valid token is present, otherwise None.

    Ownership must still be enforced by the caller when a user is present.
    Accepts both Supabase JWTs and legacy custom tokens.
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        return None

    token = credentials.credentials

    # Supabase JWT
    supabase_payload = verify_supabase_token(token)
    if supabase_payload:
        if is_token_revoked(token):
            return None
        if not supabase_payload.get("sub"):
            return None
        return _user_context_from_supabase(supabase_payload, token)

    # Legacy custom token
    if is_token_revoked(token):
        return None

    legacy_payload = verify_auth_token(token)
    if not legacy_payload or not legacy_payload.get("sub"):
        return None

    user = _auth_service.get_user_by_id(legacy_payload["sub"])
    if not user:
        return None

    return {"user": user, "session_id": legacy_payload.get("sid"), "token": token}
