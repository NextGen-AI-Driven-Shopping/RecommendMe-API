"""Legacy custom auth token helpers (transition period).

This module is kept during the migration to Supabase Auth.
New code should use Supabase-issued JWTs verified via supabase_jwt.py.

Token revocation uses Redis when available (required for multi-instance
deployments). Falls back to an in-memory denylist for local development
without Redis — not suitable for production multi-worker setups.
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
from app.core.redis_client import get_redis_client

_DENYLIST_LOCK = threading.RLock()
_token_denylist: dict[str, int] = {}  # sha256(token) -> exp timestamp (in-memory fallback)

_DENYLIST_KEY_PREFIX = "denylist:token:"


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _token_fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _prune_memory_denylist(now: int) -> None:
    expired = [key for key, exp in _token_denylist.items() if exp <= now]
    for key in expired:
        _token_denylist.pop(key, None)


def create_auth_token(*, user_id: str, session_id: str | None = None) -> str:
    """Create a signed bearer token.

    NOTE: This is a transitional helper used while Supabase Auth is being
    integrated. Once Supabase issues tokens for all flows, this function
    and its callers will be removed.
    """
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
    """Verify a legacy custom-signed token. Returns payload or None."""
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
    """Add the token to the denylist until its natural expiry.

    Uses Redis when available. Falls back to in-memory denylist.
    The in-memory fallback is not shared across workers — prefer Redis
    in any multi-instance deployment.
    """
    payload = verify_auth_token(token)
    if not payload:
        return
    exp = int(payload.get("exp", 0))
    now = int(time.time())
    if exp <= now:
        return

    ttl = exp - now
    fingerprint = _token_fingerprint(token)
    redis = get_redis_client()

    if redis:
        try:
            redis.setex(f"{_DENYLIST_KEY_PREFIX}{fingerprint}", ttl, "1")
            return
        except Exception:
            pass

    # In-memory fallback
    with _DENYLIST_LOCK:
        _prune_memory_denylist(now)
        _token_denylist[fingerprint] = exp


def is_token_revoked(token: str) -> bool:
    """Check whether the token has been added to the denylist."""
    if not token:
        return False

    fingerprint = _token_fingerprint(token)
    redis = get_redis_client()

    if redis:
        try:
            return bool(redis.exists(f"{_DENYLIST_KEY_PREFIX}{fingerprint}"))
        except Exception:
            pass

    # In-memory fallback
    with _DENYLIST_LOCK:
        _prune_memory_denylist(int(time.time()))
        return fingerprint in _token_denylist
