"""Chat session snapshot endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from app.models.responses import ChatMessageState, ChatSessionState, QueryResponse
from app.utils.session import get_session, session_exists, touch_session

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


@router.get("/{session_id}", response_model=ChatSessionState)
async def read_session(session_id: str) -> ChatSessionState:
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
    )


@router.get("/{session_id}/exists")
async def session_exists_route(session_id: str) -> dict[str, bool]:
    return {"exists": session_exists(session_id)}