"""Signed auth token helpers.

The app does not depend on an external identity provider, so we issue
compact HMAC-signed bearer tokens that can be validated by the API
without storing a server-side session for every request.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from app.config.settings import get_settings


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def create_auth_token(*, user_id: str, session_id: str | None = None) -> str:
    settings = get_settings()
    issued_at = int(time.time())
    expires_at = issued_at + settings.AUTH_TOKEN_TTL_MINUTES * 60
    payload = {
        "sub": user_id,
        "sid": session_id,
        "iat": issued_at,
        "exp": expires_at,
    }
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_segment = _b64url_encode(payload_json)
    secret = settings.AUTH_TOKEN_SECRET.encode("utf-8")
    signature = hmac.new(secret, payload_segment.encode("ascii"), hashlib.sha256).digest()
    return f"{payload_segment}.{_b64url_encode(signature)}"


def verify_auth_token(token: str) -> dict[str, Any] | None:
    settings = get_settings()
    if not token or "." not in token:
        return None

    try:
        payload_segment, signature_segment = token.split(".", 1)
        expected_signature = hmac.new(
            settings.AUTH_TOKEN_SECRET.encode("utf-8"),
            payload_segment.encode("ascii"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(expected_signature, _b64url_decode(signature_segment)):
            return None

        payload = json.loads(_b64url_decode(payload_segment).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload
    except Exception:
        return None
