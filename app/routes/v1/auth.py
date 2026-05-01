"""Authentication route handlers.

Hardening applied at this layer:
  * Per-IP sliding-window rate limit on every public auth endpoint
    (Redis-backed when Redis is available, in-memory fallback for dev).
  * Per-identifier exponential lockout on repeated failed logins
    (Redis-backed when Redis is available).
  * Generic 401 on invalid credentials — does not reveal user existence.
  * Logout revokes the bearer token via the Redis-backed denylist.

NOTE: Login / signup still issue custom bearer tokens during the
transition to Supabase Auth. Once Supabase is fully integrated the
frontend will obtain tokens directly from Supabase and these routes
will be re-evaluated. The backend already verifies Supabase JWTs —
see app/core/auth.py and app/services/supabase_jwt.py.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.config.settings import get_settings
from app.core.auth import get_current_user
from app.core.rate_limit import get_client_key, get_login_tracker, get_rate_limiter
from app.models.requests import ForgotPasswordRequest, LoginRequest, ResetPasswordRequest, SignupRequest
from app.models.responses import AuthLoginResponse, AuthSignupResponse, PasswordResetResponse
from app.services.auth_csv import (
    AuthConflictError,
    AuthCredentialsError,
    AuthNotFoundError,
    AuthValidationError,
    CsvAuthService,
)
from app.services.auth_token import create_auth_token, revoke_token
from app.services.profile_store import JsonProfileStore
from app.utils.session import update_session

router = APIRouter(prefix="/auth")
auth_service = CsvAuthService()
profile_store = JsonProfileStore()

_settings = get_settings()
_auth_rate_limiter = get_rate_limiter(
    max_requests=max(5, _settings.RATE_LIMIT_PER_MINUTE),
    window_seconds=60,
)
_login_attempts = get_login_tracker(
    max_failures=5,
    window_seconds=600,
    base_lockout_seconds=60,
    max_lockout_seconds=1800,
)


def _enforce_rate_limit(request: Request, *, scope: str) -> None:
    key = f"{scope}:{get_client_key(request)}"
    allowed, retry_after = _auth_rate_limiter.check_and_increment(key)
    if not allowed:
        wait = int(retry_after) + 1
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many requests. Try again in {wait} seconds.",
            headers={"Retry-After": str(wait)},
        )


@router.post("/signup", response_model=AuthSignupResponse)
async def signup(payload: SignupRequest, request: Request) -> AuthSignupResponse:
    _enforce_rate_limit(request, scope="signup")

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
async def login(payload: LoginRequest, request: Request) -> AuthLoginResponse:
    _enforce_rate_limit(request, scope="login")

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
        _login_attempts.assert_not_locked(identifier)
        try:
            user = auth_service.login(identifier=identifier, password=password)
        except AuthValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except (AuthNotFoundError, AuthCredentialsError) as exc:
            _login_attempts.record_failure(identifier)
            raise HTTPException(status_code=401, detail="Invalid email/phone or password.") from exc

        _login_attempts.record_success(identifier)

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
async def forgot_password(payload: ForgotPasswordRequest, request: Request) -> PasswordResetResponse:
    _enforce_rate_limit(request, scope="forgot")

    settings = get_settings()
    generic_message = "If an account exists, reset instructions were sent."

    user = auth_service.find_user_by_identifier(payload.identifier)
    if not user:
        return PasswordResetResponse(message=generic_message)

    reset_token = uuid.uuid4().hex + uuid.uuid4().hex
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
    profile_store.set_reset_token(user_id=user.user_id, reset_token=reset_token, expires_at=expires_at)

    if settings.APP_ENV.lower() != "production":
        return PasswordResetResponse(message="Reset token generated for development.", reset_token=reset_token)

    return PasswordResetResponse(message=generic_message)


@router.post("/reset-password", response_model=PasswordResetResponse)
async def reset_password(payload: ResetPasswordRequest, request: Request) -> PasswordResetResponse:
    _enforce_rate_limit(request, scope="reset")

    profile = profile_store.find_by_reset_token(payload.reset_token)
    if not profile:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")

    auth_service.update_password(user_id=profile.user_id, new_password=payload.new_password)
    profile_store.clear_reset_token(profile.user_id)
    _login_attempts.record_success(profile.user_id)
    return PasswordResetResponse(message="Password reset successful.")


@router.post("/logout")
async def logout(current=Depends(get_current_user)) -> Response:
    """Revoke the bearer token used for this request.

    For Supabase JWTs: adds the token to the Redis denylist until it
    expires naturally. The frontend should also call Supabase's sign-out
    to fully invalidate the session on Supabase's side.

    For legacy custom tokens: same revocation behaviour via the denylist.
    """
    token = current.get("token")
    if token:
        revoke_token(token)
    return Response(status_code=204)


@router.get("/me")
async def me(current=Depends(get_current_user)):
    return {"user": current["user"].model_dump(), "session_id": current["session_id"]}
