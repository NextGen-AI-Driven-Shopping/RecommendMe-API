"""
In-memory session store.

Maintains conversation history keyed by session_id (UUID string).
Sessions are evicted after SESSION_TTL_SECONDS of inactivity.

For production deployments with multiple workers, replace the
in-process dict with a Redis-backed session store to share state
across instances.
"""

import time

SESSION_TTL_SECONDS: int = 1800  # 30 minutes

# Internal store: { session_id: { "data": {...}, "last_accessed": float } }
_store: dict[str, dict] = {}


def get_session(session_id: str) -> dict | None:
    """
    Retrieve session data for a given session ID.

    Returns None if the session does not exist or has expired.
    Accessing a valid session resets its TTL.
    """
    entry = _store.get(session_id)
    if entry is None:
        return None
    if time.time() - entry["last_accessed"] > SESSION_TTL_SECONDS:
        del _store[session_id]
        return None
    entry["last_accessed"] = time.time()
    return entry["data"]


def set_session(session_id: str, data: dict) -> None:
    """Create or fully replace a session entry."""
    _store[session_id] = {"data": data, "last_accessed": time.time()}


def delete_session(session_id: str) -> None:
    """Remove a session entry by ID. No-op if the session does not exist."""
    _store.pop(session_id, None)


def session_exists(session_id: str) -> bool:
    """Return True if the session exists and has not expired."""
    return get_session(session_id) is not None
