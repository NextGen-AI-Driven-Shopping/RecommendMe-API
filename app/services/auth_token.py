"""Signed auth token helpers.

The app issues compact HMAC-signed bearer tokens that can be validated
without a server-side session per request. A small in-memory denylist
records hashes of tokens that have been logged out or otherwise revoked
so they cannot be reused before their natural expiry.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import threading
import time
from typing import Any

from app.config.settings import get_settings

_DENYLIST_LOCK = threading.RLock()
_token_denylist: dict[str, int] = {}  # sha256(token) -> exp timestamp


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _token_fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _prune_denylist(now: int) -> None:
    expired = [key for key, exp in _token_denylist.items() if exp <= now]
    for key in expired:
        _token_denylist.pop(key, None)


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


def revoke_token(token: str) -> None:
    """Add the token's fingerprint to the denylist until its natural expiry."""
    payload = verify_auth_token(token)
    if not payload:
        return
    exp = int(payload.get("exp", 0))
    if exp <= int(time.time()):
        return
    with _DENYLIST_LOCK:
        _prune_denylist(int(time.time()))
        _token_denylist[_token_fingerprint(token)] = exp


def is_token_revoked(token: str) -> bool:
    if not token:
        return False
    with _DENYLIST_LOCK:
        _prune_denylist(int(time.time()))
        return _token_fingerprint(token) in _token_denylist
