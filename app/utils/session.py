"""
In-memory session store.

Maintains conversation history keyed by session_id (UUID string).
Sessions are evicted after SESSION_TTL_SECONDS of inactivity.

For production deployments with multiple workers, replace the
in-process dict with a Redis-backed session store to share state
across instances.
"""

import copy
import threading
import time

_STORE_LOCK = threading.RLock()

SESSION_TTL_SECONDS: int = 1800  # 30 minutes

# Internal store: { session_id: { "data": {...}, "last_accessed": float } }
_store: dict[str, dict] = {}


def get_session(session_id: str) -> dict | None:
    """
    Retrieve session data for a given session ID.

    Returns None if the session does not exist or has expired.
    Accessing a valid session resets its TTL.
    """
    with _STORE_LOCK:
        entry = _store.get(session_id)
        if entry is None:
            return None
        if time.time() - entry["last_accessed"] > SESSION_TTL_SECONDS:
            del _store[session_id]
            return None
        entry["last_accessed"] = time.time()
        return copy.deepcopy(entry["data"])


def set_session(session_id: str, data: dict) -> None:
    """Create or fully replace a session entry."""
    with _STORE_LOCK:
        _store[session_id] = {"data": copy.deepcopy(data), "last_accessed": time.time()}


def update_session(session_id: str, data: dict) -> dict:
    """Merge data into an existing session entry and return the snapshot."""
    with _STORE_LOCK:
        existing = _store.get(session_id, {"data": {}, "last_accessed": time.time()})
        merged = {**existing["data"], **copy.deepcopy(data)}
        _store[session_id] = {"data": merged, "last_accessed": time.time()}
        return copy.deepcopy(merged)


def append_session_message(session_id: str, message: dict) -> dict:
    """Append a message to a session and return the updated data."""
    with _STORE_LOCK:
        existing = _store.get(session_id, {"data": {"messages": []}, "last_accessed": time.time()})
        data = copy.deepcopy(existing["data"])
        messages = list(data.get("messages") or [])
        messages.append(copy.deepcopy(message))
        data["messages"] = messages
        _store[session_id] = {"data": data, "last_accessed": time.time()}
        return copy.deepcopy(data)


def touch_session(session_id: str) -> dict | None:
    """Refresh a session TTL without altering its payload."""
    with _STORE_LOCK:
        entry = _store.get(session_id)
        if entry is None:
            return None
        if time.time() - entry["last_accessed"] > SESSION_TTL_SECONDS:
            del _store[session_id]
            return None
        entry["last_accessed"] = time.time()
        return copy.deepcopy(entry["data"])


def delete_session(session_id: str) -> None:
    """Remove a session entry by ID. No-op if the session does not exist."""
    with _STORE_LOCK:
        _store.pop(session_id, None)


def session_exists(session_id: str) -> bool:
    """Return True if the session exists and has not expired."""
    return get_session(session_id) is not None


def list_sessions_for_user(user_id: str) -> list[dict]:
    """Return non-expired sessions whose owner matches the supplied user_id."""
    if not user_id:
        return []
    now = time.time()
    results: list[dict] = []
    with _STORE_LOCK:
        stale: list[str] = []
        for sid, entry in _store.items():
            if now - entry["last_accessed"] > SESSION_TTL_SECONDS:
                stale.append(sid)
                continue
            data = entry["data"]
            if data.get("user_id") == user_id:
                snapshot = copy.deepcopy(data)
                snapshot.setdefault("session_id", sid)
                results.append(snapshot)
        for sid in stale:
            _store.pop(sid, None)

    results.sort(key=lambda s: s.get("updated_at") or s.get("created_at") or "", reverse=True)
    return results
