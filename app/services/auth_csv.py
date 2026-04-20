"""CSV-based authentication service for MVP usage."""

from __future__ import annotations

import csv
import hashlib
import hmac
import os
import re
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.config.settings import get_settings
from app.models.responses import AuthUser

EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PHONE_PATTERN = re.compile(r"^\+?[\d\s\-]{8,15}$")
_HASH_ITERATIONS = 100_000
_FILE_LOCK = threading.Lock()


class AuthValidationError(ValueError):
    """Raised when a signup/login payload fails business validation."""


class AuthConflictError(ValueError):
    """Raised when the user already exists."""


class AuthNotFoundError(ValueError):
    """Raised when login identifier does not match any account."""


class AuthCredentialsError(ValueError):
    """Raised when password does not match for a known account."""


@dataclass
class _StoredUser:
    user_id: str
    username: str
    first_name: str
    last_name: str
    email: str
    phone: str
    password_hash: str
    password_salt: str
    created_at: str

    def to_public_user(self) -> AuthUser:
        return AuthUser(
            user_id=self.user_id,
            username=self.username,
            first_name=self.first_name,
            last_name=self.last_name,
            email=self.email or None,
            phone=self.phone or None,
            created_at=self.created_at,
        )


class CsvAuthService:
    """Simple file-backed auth implementation suitable for MVP environments."""

    headers = [
        "user_id",
        "username",
        "first_name",
        "last_name",
        "email",
        "phone",
        "password_hash",
        "password_salt",
        "created_at",
    ]

    def __init__(self) -> None:
        settings = get_settings()
        configured_path = Path(settings.USERS_CSV_PATH)
        if configured_path.is_absolute():
            self.csv_path = configured_path
        else:
            backend_root = Path(__file__).resolve().parents[2]
            self.csv_path = backend_root / configured_path
        self._ensure_csv_file()

    @staticmethod
    def _normalize_phone(phone: Optional[str]) -> str:
        if not phone:
            return ""
        normalized = re.sub(r"[^\d+]", "", phone)
        if normalized.startswith("++"):
            normalized = normalized.lstrip("+")
        return normalized

    @staticmethod
    def _looks_like_email(identifier: str) -> bool:
        return bool(EMAIL_PATTERN.match(identifier))

    @staticmethod
    def _validate_contact(email: Optional[str], phone: Optional[str]) -> tuple[str, str]:
        normalized_email = (email or "").strip().lower()
        normalized_phone = CsvAuthService._normalize_phone(phone)

        if not normalized_email and not normalized_phone:
            raise AuthValidationError("Either email or phone number is required.")

        if normalized_email and not EMAIL_PATTERN.match(normalized_email):
            raise AuthValidationError("Enter a valid email address.")

        if normalized_phone and not PHONE_PATTERN.match((phone or "").strip()):
            raise AuthValidationError("Enter a valid phone number.")

        return normalized_email, normalized_phone

    @staticmethod
    def _hash_password(password: str, salt_hex: str) -> str:
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            _HASH_ITERATIONS,
        )
        return digest.hex()

    @staticmethod
    def _new_salt() -> str:
        return os.urandom(16).hex()

    def _ensure_csv_file(self) -> None:
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        if self.csv_path.exists():
            return
        with self.csv_path.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=self.headers)
            writer.writeheader()

    def _read_users(self) -> list[_StoredUser]:
        self._ensure_csv_file()
        users: list[_StoredUser] = []
        with self.csv_path.open("r", newline="", encoding="utf-8") as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:
                users.append(
                    _StoredUser(
                        user_id=row.get("user_id", ""),
                        username=row.get("username", ""),
                        first_name=row.get("first_name", ""),
                        last_name=row.get("last_name", ""),
                        email=row.get("email", ""),
                        phone=row.get("phone", ""),
                        password_hash=row.get("password_hash", ""),
                        password_salt=row.get("password_salt", ""),
                        created_at=row.get("created_at", ""),
                    )
                )
        return users

    def _append_user(self, user: _StoredUser) -> None:
        with self.csv_path.open("a", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=self.headers)
            writer.writerow(
                {
                    "user_id": user.user_id,
                    "username": user.username,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "email": user.email,
                    "phone": user.phone,
                    "password_hash": user.password_hash,
                    "password_salt": user.password_salt,
                    "created_at": user.created_at,
                }
            )

    def signup(
        self,
        *,
        username: str,
        first_name: str,
        last_name: str,
        email: Optional[str],
        phone: Optional[str],
        password: str,
    ) -> AuthUser:
        normalized_email, normalized_phone = self._validate_contact(email, phone)
        if len(password) < 6:
            raise AuthValidationError("Password must be at least 6 characters.")

        with _FILE_LOCK:
            users = self._read_users()

            for existing in users:
                if normalized_email and existing.email.lower() == normalized_email:
                    raise AuthConflictError("An account with this email already exists.")
                if normalized_phone and existing.phone == normalized_phone:
                    raise AuthConflictError("An account with this phone number already exists.")

            salt = self._new_salt()
            password_hash = self._hash_password(password, salt)
            stored = _StoredUser(
                user_id=str(uuid.uuid4()),
                username=username.strip(),
                first_name=first_name.strip(),
                last_name=last_name.strip(),
                email=normalized_email,
                phone=normalized_phone,
                password_hash=password_hash,
                password_salt=salt,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            self._append_user(stored)

        return stored.to_public_user()

    def login(self, *, identifier: str, password: str) -> AuthUser:
        identifier = identifier.strip()
        if not identifier:
            raise AuthValidationError("Email/phone is required.")

        with _FILE_LOCK:
            users = self._read_users()

        email_match = identifier.lower()
        phone_match = self._normalize_phone(identifier)

        found_user: Optional[_StoredUser] = None
        for user in users:
            if self._looks_like_email(identifier):
                if user.email.lower() == email_match:
                    found_user = user
                    break
            else:
                if user.phone == phone_match:
                    found_user = user
                    break

        if not found_user:
            raise AuthNotFoundError("No account found for this email/phone.")

        expected_hash = self._hash_password(password, found_user.password_salt)
        if not hmac.compare_digest(expected_hash, found_user.password_hash):
            raise AuthCredentialsError("Invalid password.")

        return found_user.to_public_user()

    def get_or_create_dev_user(self, *, identifier: Optional[str] = None) -> AuthUser:
        """Return a reusable development user when auth validation is intentionally relaxed."""
        fallback_email = "dev@recommendme.local"
        fallback_phone = "+910000000000"
        chosen_identifier = (identifier or "").strip()

        with _FILE_LOCK:
            users = self._read_users()

            if chosen_identifier:
                email_match = chosen_identifier.lower()
                phone_match = self._normalize_phone(chosen_identifier)
                for existing in users:
                    if self._looks_like_email(chosen_identifier):
                        if existing.email.lower() == email_match:
                            return existing.to_public_user()
                    else:
                        if existing.phone == phone_match:
                            return existing.to_public_user()

            for existing in users:
                if existing.email.lower() == fallback_email or existing.phone == fallback_phone:
                    return existing.to_public_user()

            salt = self._new_salt()
            password_hash = self._hash_password("recommendme-dev", salt)
            stored = _StoredUser(
                user_id=str(uuid.uuid4()),
                username="dev-user",
                first_name="Dev",
                last_name="User",
                email=fallback_email,
                phone=fallback_phone,
                password_hash=password_hash,
                password_salt=salt,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            self._append_user(stored)

        return stored.to_public_user()

    def find_user_by_identifier(self, identifier: str) -> Optional[AuthUser]:
        identifier = identifier.strip()
        if not identifier:
            return None

        with _FILE_LOCK:
            users = self._read_users()

        email_match = identifier.lower()
        phone_match = self._normalize_phone(identifier)
        for user in users:
            if self._looks_like_email(identifier):
                if user.email.lower() == email_match:
                    return user.to_public_user()
            elif user.phone == phone_match:
                return user.to_public_user()
        return None

    def update_password(self, *, user_id: str, new_password: str) -> None:
        if len(new_password) < 6:
            raise AuthValidationError("Password must be at least 6 characters.")

        with _FILE_LOCK:
            users = self._read_users()
            salt = self._new_salt()
            password_hash = self._hash_password(new_password, salt)

            updated_rows = []
            updated = False
            for user in users:
                if user.user_id == user_id:
                    user.password_salt = salt
                    user.password_hash = password_hash
                    updated = True
                updated_rows.append(user)

            if not updated:
                raise AuthNotFoundError("No account found for this user.")

            with self.csv_path.open("w", newline="", encoding="utf-8") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=self.headers)
                writer.writeheader()
                for user in updated_rows:
                    writer.writerow(
                        {
                            "user_id": user.user_id,
                            "username": user.username,
                            "first_name": user.first_name,
                            "last_name": user.last_name,
                            "email": user.email,
                            "phone": user.phone,
                            "password_hash": user.password_hash,
                            "password_salt": user.password_salt,
                            "created_at": user.created_at,
                        }
                    )

    def get_user_by_id(self, user_id: str) -> Optional[AuthUser]:
        with _FILE_LOCK:
            users = self._read_users()

        for user in users:
            if user.user_id == user_id:
                return user.to_public_user()
        return None
