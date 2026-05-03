"""Authentication dependencies and helpers."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.services.auth_csv import CsvAuthService
from app.services.auth_token import verify_auth_token

_bearer_scheme = HTTPBearer(auto_error=False)
_auth_service = CsvAuthService()


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme)):
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token.")

    payload = verify_auth_token(credentials.credentials)
    if not payload or not payload.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token.")

    user = _auth_service.get_user_by_id(payload["sub"])
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")

    return {"user": user, "session_id": payload.get("sid")}


def get_optional_user(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme)):
    """Returns the current user if a valid token is present, otherwise None.

    Use this on endpoints that are accessible anonymously but should enforce
    ownership when the session belongs to an authenticated user.
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        return None

    payload = verify_auth_token(credentials.credentials)
    if not payload or not payload.get("sub"):
        return None

    user = _auth_service.get_user_by_id(payload["sub"])
    if not user:
        return None

    return {"user": user, "session_id": payload.get("sid")}
