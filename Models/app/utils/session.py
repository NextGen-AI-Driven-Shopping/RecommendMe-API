"""
In-memory session store for the RecommendMe API.

Provides a thread-safe, dict-based session manager keyed by
``session_id`` (UUID string). Designed for the stateless MVP —
will be replaced by a database-backed store in v2.
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field

from app.models.requests import ConversationMessage
from app.core.exceptions import SessionExpiredError, SessionNotFoundError


# ---------------------------------------------------------------------------
# Session data model
# ---------------------------------------------------------------------------

class SessionData(BaseModel):
    """State for a single user session."""

    session_id: str = Field(
        ...,
        description="Unique session identifier (UUID string).",
    )
    messages: list[ConversationMessage] = Field(
        default_factory=list,
        description="Ordered conversation history.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the session was created.",
    )
    last_active: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last time the session received a message.",
    )


# ---------------------------------------------------------------------------
# Session store
# ---------------------------------------------------------------------------

class SessionStore:
    """
    Thread-safe, in-memory session store.

    All public methods acquire a lock to ensure safe concurrent access
    from FastAPI's async request handlers.

    Parameters
    ----------
    default_ttl_minutes : int
        Default time-to-live for sessions (used by ``expire_stale``).
    max_messages : int
        Maximum messages per session (prompt-injection guard).
    """

    def __init__(
        self,
        default_ttl_minutes: int = 30,
        max_messages: int = 20,
    ) -> None:
        self._store: dict[str, SessionData] = {}
        self._lock = threading.Lock()
        self.default_ttl_minutes = default_ttl_minutes
        self.max_messages = max_messages

    # ----- Create -----

    def create(self) -> SessionData:
        """
        Create a new session with a freshly generated UUID.

        Returns
        -------
        SessionData
            The newly created session.
        """
        session_id = str(uuid.uuid4())
        session = SessionData(session_id=session_id)
        with self._lock:
            self._store[session_id] = session
        return session

    # ----- Read -----

    def get(self, session_id: str) -> Optional[SessionData]:
        """
        Retrieve a session by its ID.

        Returns ``None`` if the session does not exist (does *not* raise).
        """
        with self._lock:
            return self._store.get(session_id)

    def get_or_raise(self, session_id: str) -> SessionData:
        """
        Retrieve a session by its ID, raising if it doesn't exist.

        Raises
        ------
        SessionNotFoundError
            If the session_id is not in the store.
        """
        session = self.get(session_id)
        if session is None:
            raise SessionNotFoundError()
        return session

    # ----- Update -----

    def update(
        self,
        session_id: str,
        message: ConversationMessage,
    ) -> SessionData:
        """
        Append a message to an existing session and refresh ``last_active``.

        If the session's message count would exceed ``max_messages``,
        the oldest messages are dropped (FIFO).

        Parameters
        ----------
        session_id : str
            The session to update.
        message : ConversationMessage
            The message to append.

        Returns
        -------
        SessionData
            The updated session.

        Raises
        ------
        SessionNotFoundError
            If the session_id is not in the store.
        """
        with self._lock:
            session = self._store.get(session_id)
            if session is None:
                raise SessionNotFoundError()

            session.messages.append(message)

            # Enforce message cap — drop oldest
            if len(session.messages) > self.max_messages:
                session.messages = session.messages[-self.max_messages :]

            session.last_active = datetime.now(timezone.utc)
            return session

    # ----- Expire -----

    def expire_stale(self, ttl_minutes: int | None = None) -> int:
        """
        Remove sessions that have been inactive longer than ``ttl_minutes``.

        Parameters
        ----------
        ttl_minutes : int, optional
            Override for the default TTL. If ``None``, uses
            ``self.default_ttl_minutes``.

        Returns
        -------
        int
            Number of sessions removed.
        """
        ttl = ttl_minutes if ttl_minutes is not None else self.default_ttl_minutes
        now = datetime.now(timezone.utc)
        removed = 0
        with self._lock:
            expired_ids = [
                sid
                for sid, session in self._store.items()
                if (now - session.last_active).total_seconds() > ttl * 60
            ]
            for sid in expired_ids:
                del self._store[sid]
                removed += 1
        return removed

    # ----- Helpers -----

    def resolve_session(self, session_id: str | None) -> SessionData:
        """
        Resolve or create a session.

        If ``session_id`` is provided and exists, return it.
        If ``session_id`` is provided but expired/missing, raise.
        If ``session_id`` is ``None``, create a new session.

        Parameters
        ----------
        session_id : str or None
            The client-provided session ID, or ``None``.

        Returns
        -------
        SessionData
            An existing or new session.
        """
        if session_id is None:
            return self.create()
        return self.get_or_raise(session_id)

    @property
    def active_count(self) -> int:
        """Return the number of active sessions."""
        with self._lock:
            return len(self._store)

    def clear(self) -> None:
        """Remove all sessions. Primarily for testing."""
        with self._lock:
            self._store.clear()
