"""User profile management routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.auth import get_current_user
from app.models.requests import ProfileUpdateRequest
from app.models.responses import AvatarOptionsResponse, ProfileResponse, UserProfile
from app.services.profile_store import JsonProfileStore

router = APIRouter(prefix="/profile")
profile_store = JsonProfileStore()


def _load_profile(user_id: str, username: str, email: str) -> UserProfile:
    profile = profile_store.upsert_default(user_id=user_id, username=username, email=email)
    return profile


@router.get("", response_model=ProfileResponse)
async def get_profile(current=Depends(get_current_user)) -> ProfileResponse:
    user = current["user"]
    profile = _load_profile(user.user_id, user.username, user.email or "")
    return ProfileResponse(profile=UserProfile(**profile.to_public_dict()))


@router.post("", response_model=ProfileResponse)
async def create_profile(payload: ProfileUpdateRequest, current=Depends(get_current_user)) -> ProfileResponse:
    user = current["user"]
    profile = _load_profile(user.user_id, user.username, user.email or "")
    updated = profile_store.update(
        user.user_id,
        username=payload.username or profile.username,
        gender=payload.gender or profile.gender,
        age=payload.age if payload.age is not None else profile.age,
        interests=payload.interests if payload.interests is not None else profile.interests,
        about=payload.about if payload.about is not None else profile.about,
        avatar_url=payload.avatar_url or profile.avatar_url,
        avatar_file_path=payload.avatar_file_path or profile.avatar_file_path,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Profile not found.")
    return ProfileResponse(profile=UserProfile(**updated.to_public_dict()))


@router.put("/update", response_model=ProfileResponse)
async def update_profile(payload: ProfileUpdateRequest, current=Depends(get_current_user)) -> ProfileResponse:
    user = current["user"]
    existing = profile_store.get(user.user_id) or _load_profile(user.user_id, user.username, user.email or "")
    updated = profile_store.update(
        user.user_id,
        username=payload.username or existing.username,
        gender=payload.gender or existing.gender,
        age=payload.age if payload.age is not None else existing.age,
        interests=payload.interests if payload.interests is not None else existing.interests,
        about=payload.about if payload.about is not None else existing.about,
        avatar_url=payload.avatar_url or existing.avatar_url,
        avatar_file_path=payload.avatar_file_path or existing.avatar_file_path,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Profile not found.")
    return ProfileResponse(profile=UserProfile(**updated.to_public_dict()))


@router.get("/avatars", response_model=AvatarOptionsResponse)
async def list_avatars() -> AvatarOptionsResponse:
    return AvatarOptionsResponse(avatars=[
        *profile_store.list_default_avatars(),
    ])


@router.post("/avatar/upload", response_model=ProfileResponse)
async def upload_avatar(image: UploadFile = File(...), current=Depends(get_current_user)) -> ProfileResponse:
    raise HTTPException(
        status_code=400,
        detail="Image uploads are disabled. Choose an avatar URL via /profile or /profile/update.",
    )


