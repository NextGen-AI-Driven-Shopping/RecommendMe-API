"""Authentication route handlers for CSV-backed MVP auth."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from app.models.requests import LoginRequest, SignupRequest
from app.models.responses import AuthLoginResponse, AuthSignupResponse
from app.services.auth_csv import (
    AuthConflictError,
    AuthCredentialsError,
    AuthNotFoundError,
    AuthValidationError,
    CsvAuthService,
)

router = APIRouter(prefix="/auth")
auth_service = CsvAuthService()


@router.post("/signup", response_model=AuthSignupResponse)
async def signup(payload: SignupRequest) -> AuthSignupResponse:
    """Create a new user account in CSV storage."""
    try:
        user = auth_service.signup(
            username=payload.username,
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
            phone=payload.phone,
            password=payload.password,
        )
    except AuthValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AuthConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return AuthSignupResponse(
        message="Account created successfully.",
        token=str(uuid.uuid4()),
        user=user,
    )


@router.post("/login", response_model=AuthLoginResponse)
async def login(payload: LoginRequest) -> AuthLoginResponse:
    """Validate credentials against CSV-backed user records."""
    try:
        user = auth_service.login(identifier=payload.identifier, password=payload.password)
    except AuthValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AuthNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AuthCredentialsError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    return AuthLoginResponse(
        message="Login successful.",
        token=str(uuid.uuid4()),
        user=user,
    )
