"""Authentication route handlers for CSV-backed MVP auth."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import get_current_user
from app.config.settings import get_settings
from app.models.requests import ForgotPasswordRequest, LoginRequest, ResetPasswordRequest, SignupRequest
from app.models.responses import AuthLoginResponse, AuthSignupResponse, PasswordResetResponse
from app.services.auth_csv import (
    AuthConflictError,
    AuthCredentialsError,
    AuthNotFoundError,
    AuthValidationError,
    CsvAuthService,
)
from app.services.auth_token import create_auth_token
from app.services.profile_store import JsonProfileStore
from app.utils.session import update_session

router = APIRouter(prefix="/auth")
auth_service = CsvAuthService()
profile_store = JsonProfileStore()


@router.post("/signup", response_model=AuthSignupResponse)
async def signup(payload: SignupRequest) -> AuthSignupResponse:
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

    profile = profile_store.upsert_default(
        user_id=user.user_id,
        username=user.username,
        email=user.email or "",
    )
    token = create_auth_token(user_id=user.user_id, session_id=payload.session_id)

    return AuthSignupResponse(
        message="Account created successfully.",
        token=token,
        user=user,
        session_id=payload.session_id,
        profile=profile.to_public_dict(),
    )


@router.post("/login", response_model=AuthLoginResponse)
async def login(payload: LoginRequest) -> AuthLoginResponse:
    settings = get_settings()
    identifier = (payload.identifier or "").strip()
    password = payload.password or ""

    allow_dev_bypass = (
        settings.APP_ENV.lower() == "development"
        and settings.ALLOW_DEV_LOGIN_BYPASS
    )

    if allow_dev_bypass and (not identifier or not password):
        user = auth_service.get_or_create_dev_user(identifier=identifier or None)
    else:
        try:
            user = auth_service.login(identifier=identifier, password=password)
        except AuthValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except AuthNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except AuthCredentialsError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

    profile = profile_store.upsert_default(
        user_id=user.user_id,
        username=user.username,
        email=user.email or "",
    )

    if payload.session_id:
        update_session(
            payload.session_id,
            {
                "session_id": payload.session_id,
                "user_id": user.user_id,
                "status": "authenticated",
            },
        )

    return AuthLoginResponse(
        message="Login successful.",
        token=create_auth_token(user_id=user.user_id, session_id=payload.session_id),
        user=user,
        session_id=payload.session_id,
        profile=profile.to_public_dict(),
    )


@router.post("/forgot-password", response_model=PasswordResetResponse)
async def forgot_password(payload: ForgotPasswordRequest) -> PasswordResetResponse:
    settings = get_settings()
    generic_message = "If an account exists, reset instructions were sent."

    user = auth_service.find_user_by_identifier(payload.identifier)
    if not user:
        return PasswordResetResponse(message=generic_message)

    reset_token = str(uuid.uuid4())
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
    profile_store.set_reset_token(user_id=user.user_id, reset_token=reset_token, expires_at=expires_at)

    if settings.APP_ENV.lower() != "production":
        return PasswordResetResponse(message="Reset token generated for development.", reset_token=reset_token)

    return PasswordResetResponse(message=generic_message)


@router.post("/reset-password", response_model=PasswordResetResponse)
async def reset_password(payload: ResetPasswordRequest) -> PasswordResetResponse:
    profile = profile_store.find_by_reset_token(payload.reset_token)
    if not profile:
        raise HTTPException(status_code=404, detail="Reset token not found or expired.")

    auth_service.update_password(user_id=profile.user_id, new_password=payload.new_password)
    profile_store.clear_reset_token(profile.user_id)
    return PasswordResetResponse(message="Password reset successful.")


@router.get("/me")
async def me(current=Depends(get_current_user)):
    return {"user": current["user"].model_dump(), "session_id": current["session_id"]}
