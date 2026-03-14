"""
Unit tests for app.utils.session — SessionStore
"""

import time

import pytest

from app.models.requests import ConversationMessage
from app.utils.session import SessionData, SessionStore
from app.core.exceptions import SessionNotFoundError


# =====================================================================
# SessionData model
# =====================================================================

class TestSessionData:

    def test_defaults(self):
        sd = SessionData(session_id="abc-123")
        assert sd.session_id == "abc-123"
        assert sd.messages == []
        assert sd.created_at is not None
        assert sd.last_active is not None

    def test_with_messages(self):
        msg = ConversationMessage(role="user", content="hello there friend")
        sd = SessionData(session_id="x", messages=[msg])
        assert len(sd.messages) == 1


# =====================================================================
# SessionStore
# =====================================================================

class TestSessionStore:

    @pytest.fixture
    def store(self):
        return SessionStore(default_ttl_minutes=30, max_messages=5)

    # ----- create -----

    def test_create_returns_session(self, store):
        session = store.create()
        assert session.session_id is not None
        assert session.messages == []

    def test_create_unique_ids(self, store):
        s1 = store.create()
        s2 = store.create()
        assert s1.session_id != s2.session_id

    def test_create_increments_count(self, store):
        assert store.active_count == 0
        store.create()
        assert store.active_count == 1
        store.create()
        assert store.active_count == 2

    # ----- get -----

    def test_get_existing(self, store):
        session = store.create()
        retrieved = store.get(session.session_id)
        assert retrieved is not None
        assert retrieved.session_id == session.session_id

    def test_get_nonexistent_returns_none(self, store):
        assert store.get("nonexistent-id") is None

    # ----- get_or_raise -----

    def test_get_or_raise_existing(self, store):
        session = store.create()
        retrieved = store.get_or_raise(session.session_id)
        assert retrieved.session_id == session.session_id

    def test_get_or_raise_nonexistent_raises(self, store):
        with pytest.raises(SessionNotFoundError):
            store.get_or_raise("does-not-exist")

    # ----- update -----

    def test_update_appends_message(self, store):
        session = store.create()
        msg = ConversationMessage(role="user", content="I want a tent for camping")
        updated = store.update(session.session_id, msg)
        assert len(updated.messages) == 1
        assert updated.messages[0].content == "I want a tent for camping"

    def test_update_refreshes_last_active(self, store):
        session = store.create()
        original_time = session.last_active
        time.sleep(0.01)  # Ensure time difference
        msg = ConversationMessage(role="user", content="I need a new laptop")
        updated = store.update(session.session_id, msg)
        assert updated.last_active >= original_time

    def test_update_nonexistent_raises(self, store):
        msg = ConversationMessage(role="user", content="test message here please")
        with pytest.raises(SessionNotFoundError):
            store.update("nonexistent", msg)

    def test_update_enforces_max_messages(self, store):
        """Messages beyond max_messages are dropped (FIFO)."""
        session = store.create()
        for i in range(7):
            msg = ConversationMessage(role="user", content=f"message number {i}")
            store.update(session.session_id, msg)

        updated = store.get(session.session_id)
        assert len(updated.messages) == 5  # max_messages=5 in fixture
        # Oldest messages should have been dropped
        assert updated.messages[0].content == "message number 2"
        assert updated.messages[-1].content == "message number 6"

    # ----- expire_stale -----

    def test_expire_stale_removes_old_sessions(self, store):
        session = store.create()
        # Manually backdate the session
        session.last_active = session.last_active.replace(year=2020)
        removed = store.expire_stale(ttl_minutes=1)
        assert removed == 1
        assert store.active_count == 0

    def test_expire_stale_keeps_active_sessions(self, store):
        store.create()
        removed = store.expire_stale(ttl_minutes=30)
        assert removed == 0
        assert store.active_count == 1

    def test_expire_stale_uses_default_ttl(self, store):
        store.create()
        removed = store.expire_stale()  # Uses default_ttl_minutes=30
        assert removed == 0

    # ----- resolve_session -----

    def test_resolve_none_creates_new(self, store):
        session = store.resolve_session(None)
        assert session.session_id is not None
        assert store.active_count == 1

    def test_resolve_existing_returns_it(self, store):
        session = store.create()
        resolved = store.resolve_session(session.session_id)
        assert resolved.session_id == session.session_id

    def test_resolve_unknown_raises(self, store):
        with pytest.raises(SessionNotFoundError):
            store.resolve_session("unknown-id")

    # ----- clear -----

    def test_clear_removes_all(self, store):
        store.create()
        store.create()
        assert store.active_count == 2
        store.clear()
        assert store.active_count == 0
