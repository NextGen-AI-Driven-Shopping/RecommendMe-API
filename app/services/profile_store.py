"""Persistent user profile store backed by JSON on disk."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.config.settings import get_settings

_PROFILE_LOCK = threading.RLock()
_DEFAULT_AVATAR = "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&w=512&q=80"


@dataclass
class UserProfile:
    user_id: str
    username: str
    email: str
    gender: str = "Other"
    age: Optional[int] = None
    interests: list[str] | None = None
    about: str = ""
    avatar_url: str = _DEFAULT_AVATAR
    avatar_file_path: str | None = None
    password_reset_token: str | None = None
    password_reset_expires_at: str | None = None
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        self.interests = self._normalize_interests(self.interests)

    @staticmethod
    def _normalize_interests(value: list[str] | str | None) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return []

    def to_public_dict(self) -> dict:
        data = self.to_storage_dict()
        data.pop("password_reset_token", None)
        data.pop("password_reset_expires_at", None)
        return data

    def to_storage_dict(self) -> dict:
        data = asdict(self)
        data["interests"] = self._normalize_interests(data.get("interests"))
        return data


class JsonProfileStore:
    def __init__(self) -> None:
        settings = get_settings()
        configured_path = Path(settings.PROFILE_STORE_PATH)
        if configured_path.is_absolute():
            self.store_path = configured_path
        else:
            backend_root = Path(__file__).resolve().parents[2]
            self.store_path = backend_root / configured_path
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.store_path.exists():
            self._write_all({})

    def _read_all(self) -> dict[str, dict]:
        if not self.store_path.exists():
            return {}
        with self.store_path.open("r", encoding="utf-8") as handle:
            raw = handle.read().strip()
            if not raw:
                return {}
            return json.loads(raw)

    def _write_all(self, payload: dict[str, dict]) -> None:
        with self.store_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)

    def get(self, user_id: str) -> Optional[UserProfile]:
        with _PROFILE_LOCK:
            data = self._read_all().get(user_id)
        if not data:
            return None
        data["interests"] = UserProfile._normalize_interests(data.get("interests"))
        return UserProfile(**data)

    def upsert_default(self, *, user_id: str, username: str, email: str) -> UserProfile:
        existing = self.get(user_id)
        if existing:
            return existing
        profile = UserProfile(
            user_id=user_id,
            username=username,
            email=email,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        self.save(profile)
        return profile

    def save(self, profile: UserProfile) -> UserProfile:
        with _PROFILE_LOCK:
            data = self._read_all()
            profile.updated_at = datetime.now(timezone.utc).isoformat()
            if not profile.created_at:
                profile.created_at = profile.updated_at
            data[profile.user_id] = profile.to_storage_dict()
            self._write_all(data)
        return profile

    def update(self, user_id: str, **fields) -> Optional[UserProfile]:
        existing = self.get(user_id)
        if not existing:
            return None
        for key, value in fields.items():
            if hasattr(existing, key) and value is not None:
                setattr(existing, key, value)
        return self.save(existing)

    def set_reset_token(self, *, user_id: str, reset_token: str, expires_at: str) -> Optional[UserProfile]:
        return self.update(user_id, password_reset_token=reset_token, password_reset_expires_at=expires_at)

    def find_by_reset_token(self, reset_token: str) -> Optional[UserProfile]:
        now = datetime.now(timezone.utc)
        with _PROFILE_LOCK:
            profiles = self._read_all()

        for profile_data in profiles.values():
            if profile_data.get("password_reset_token") != reset_token:
                continue

            expires_at_raw = profile_data.get("password_reset_expires_at")
            if not expires_at_raw:
                continue

            try:
                expires_at = datetime.fromisoformat(str(expires_at_raw))
            except ValueError:
                continue

            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)

            if expires_at < now:
                continue

            return UserProfile(**profile_data)

        return None

    def clear_reset_token(self, user_id: str) -> Optional[UserProfile]:
        return self.update(user_id, password_reset_token=None, password_reset_expires_at=None)

    def list_default_avatars(self) -> list[dict[str, str]]:
        return [
            {"id": "male-1", "gender": "Male", "url": "https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?auto=format&fit=crop&w=256&q=80"},
            {"id": "male-2", "gender": "Male", "url": "https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?auto=format&fit=crop&w=256&q=80"},
            {"id": "female-1", "gender": "Female", "url": "https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=256&q=80"},
            {"id": "female-2", "gender": "Female", "url": "https://images.unsplash.com/photo-1438761681033-6461ffad8d80?auto=format&fit=crop&w=256&q=80"},
        ]
