"""User profile management routes."""

from __future__ import annotations

from pathlib import Path
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.config.settings import get_settings
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


_ALLOWED_AVATAR_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
_AVATAR_MAGIC_BYTES = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"RIFF", "image/webp"),
)


@router.post("/avatar/upload", response_model=ProfileResponse)
async def upload_avatar(image: UploadFile = File(...), current=Depends(get_current_user)) -> ProfileResponse:
    if image.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(status_code=400, detail="Only JPG, PNG, and WEBP images are allowed.")

    contents = await image.read()
    if len(contents) > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Avatar image must be 2MB or smaller.")

    if not any(contents.startswith(magic) for magic, _ in _AVATAR_MAGIC_BYTES):
        raise HTTPException(status_code=400, detail="Uploaded file is not a recognised image.")

    settings = get_settings()
    upload_root = Path(settings.PROFILE_UPLOAD_DIR)
    if not upload_root.is_absolute():
        backend_root = Path(__file__).resolve().parents[2]
        upload_root = backend_root / upload_root
    upload_root = upload_root.resolve()
    upload_root.mkdir(parents=True, exist_ok=True)

    raw_ext = Path(image.filename or "avatar.png").suffix.lower()
    file_ext = raw_ext if raw_ext in _ALLOWED_AVATAR_EXTENSIONS else ".png"
    file_name = f"{current['user'].user_id}-{uuid.uuid4().hex}{file_ext}"
    file_path = (upload_root / file_name).resolve()

    # Defence-in-depth: refuse to write outside the configured upload root.
    if upload_root not in file_path.parents and file_path.parent != upload_root:
        raise HTTPException(status_code=400, detail="Invalid upload path.")
    file_path.write_bytes(contents)

    updated = profile_store.update(current["user"].user_id, avatar_file_path=str(file_path), avatar_url=None)
    if updated is None:
        raise HTTPException(status_code=404, detail="Profile not found.")
    return ProfileResponse(profile=UserProfile(**updated.to_public_dict()))


