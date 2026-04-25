"""Chat session snapshot endpoints.

Ownership rules:
  * Anonymous sessions (created without a logged-in user) are accessible
    to any caller that knows the session_id — they are short-lived
    UUIDs that are not enumerable.
  * Once a session has a `user_id` attached, only that user may read,
    feedback or save against it.

These rules are enforced via `_assert_session_ownership`, which short
circuits with 401/403 before any data is returned. Endpoints that
mutate state (`feedback`, `save`) refuse to run against a non-existent
session_id so an unauthenticated client cannot fabricate sessions.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import get_current_user, get_optional_user
from app.models.requests import SessionFeedbackRequest, SessionSaveRequest
from app.models.responses import ChatMessageState, ChatSessionState, QueryResponse
from app.models.responses import SessionFeedbackResponse, SessionSaveResponse
from app.utils.session import get_session, list_sessions_for_user, session_exists, set_session, touch_session

router = APIRouter(prefix="/sessions")


def _normalize_clarification_answers(raw_answers) -> list[dict] | None:
    if raw_answers is None:
        return None

    normalized: list[dict] = []
    for answer in raw_answers:
        if isinstance(answer, dict):
            normalized.append(
                {
                    "question": str(answer.get("question", "")).strip(),
                    "answer": str(answer.get("answer", "")).strip(),
                }
            )
            continue

        if hasattr(answer, "model_dump"):
            dumped = answer.model_dump()
            normalized.append(
                {
                    "question": str(dumped.get("question", "")).strip(),
                    "answer": str(dumped.get("answer", "")).strip(),
                }
            )
            continue

        normalized.append(
            {
                "question": str(getattr(answer, "question", "")).strip(),
                "answer": str(getattr(answer, "answer", "")).strip(),
            }
        )

    return normalized


def _assert_session_ownership(session: dict | None, current) -> None:
    """Raise 401/403 if the session belongs to a user and the caller is not that user."""
    if session is None:
        return
    session_user_id = session.get("user_id")
    if not session_user_id:
        return
    if not current:
        raise HTTPException(status_code=401, detail="Authentication required to access this session.")
    if current["user"].user_id != session_user_id:
        raise HTTPException(status_code=403, detail="Access denied.")


@router.get("/me")
async def list_my_sessions(current=Depends(get_current_user)) -> dict:
    """Return summary metadata for every session owned by the caller."""
    sessions = list_sessions_for_user(current["user"].user_id)
    return {
        "sessions": [
            {
                "session_id": s.get("session_id"),
                "title": s.get("title", "New Chat"),
                "status": s.get("status", "new"),
                "created_at": s.get("created_at"),
                "updated_at": s.get("updated_at"),
            }
            for s in sessions
        ]
    }


@router.get("/{session_id}", response_model=ChatSessionState)
async def read_session(session_id: str, current=Depends(get_optional_user)) -> ChatSessionState:
    snapshot = get_session(session_id)

    if snapshot is None:
        now = datetime.now(timezone.utc).isoformat()
        return ChatSessionState(
            session_id=session_id,
            status="new",
            title="New Chat",
            user_id=None,
            messages=[],
            created_at=now,
            updated_at=now,
            original_query=None,
            pending_questions=None,
            current_question_index=None,
            clarification_answers=None,
            latest_response=None,
        )

    _assert_session_ownership(snapshot, current)
    touch_session(session_id)

    messages = [ChatMessageState(**message) for message in snapshot.get("messages", [])]
    latest_response = snapshot.get("latest_response")
    parsed_latest_response = QueryResponse(**latest_response) if latest_response else None

    return ChatSessionState(
        session_id=session_id,
        status=snapshot.get("status", "new"),
        title=snapshot.get("title", "New Chat"),
        user_id=snapshot.get("user_id"),
        messages=messages,
        created_at=snapshot.get("created_at") or datetime.now(timezone.utc).isoformat(),
        updated_at=snapshot.get("updated_at") or datetime.now(timezone.utc).isoformat(),
        original_query=snapshot.get("original_query"),
        pending_questions=snapshot.get("pending_questions"),
        current_question_index=snapshot.get("current_question_index"),
        clarification_answers=_normalize_clarification_answers(snapshot.get("clarification_answers")),
        latest_response=parsed_latest_response,
        feedback_count=len(snapshot.get("feedback_events") or []),
        saved_count=len(snapshot.get("saved_recommendations") or []),
    )


@router.get("/{session_id}/exists")
async def session_exists_route(session_id: str, current=Depends(get_optional_user)) -> dict[str, bool]:
    """Existence probe.

    For sessions owned by an authenticated user, the caller must be that
    user — otherwise the response indicates the session does not exist
    so we do not leak the presence of another user's session.
    """
    snapshot = get_session(session_id)
    if snapshot is None:
        return {"exists": False}

    owner_id = snapshot.get("user_id")
    if owner_id and (not current or current["user"].user_id != owner_id):
        return {"exists": False}

    return {"exists": session_exists(session_id)}


@router.post("/{session_id}/feedback", response_model=SessionFeedbackResponse)
async def store_session_feedback(
    session_id: str,
    payload: SessionFeedbackRequest,
    current=Depends(get_optional_user),
) -> SessionFeedbackResponse:
    snapshot = get_session(session_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    _assert_session_ownership(snapshot, current)

    feedback_events = list(snapshot.get("feedback_events") or [])
    feedback_events.append(
        {
            "sentiment": payload.sentiment,
            "rating": payload.rating,
            "comment": payload.comment,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )

    set_session(
        session_id,
        {
            **snapshot,
            "feedback_events": feedback_events,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    return SessionFeedbackResponse(
        session_id=session_id,
        message="Feedback saved.",
        feedback_count=len(feedback_events),
    )


@router.post("/{session_id}/save", response_model=SessionSaveResponse)
async def save_session_recommendation(
    session_id: str,
    payload: SessionSaveRequest,
    current=Depends(get_optional_user),
) -> SessionSaveResponse:
    snapshot = get_session(session_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    _assert_session_ownership(snapshot, current)

    saved_recommendations = list(snapshot.get("saved_recommendations") or [])
    saved_recommendations.append(
        {
            "note": payload.note,
            "category": snapshot.get("category"),
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "latest_response": snapshot.get("latest_response"),
        }
    )

    set_session(
        session_id,
        {
            **snapshot,
            "saved_recommendations": saved_recommendations,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    return SessionSaveResponse(
        session_id=session_id,
        message="Recommendation saved.",
        saved_count=len(saved_recommendations),
    )
