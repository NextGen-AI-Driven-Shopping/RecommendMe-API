"""Post-results chat mode route handlers."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from app.models.requests import ChatModeRequest
from app.models.responses import ChatModeResponse
from app.services.chat_mode import answer_chat_followup
from app.services.profile_store import JsonProfileStore
from app.utils.session import get_session, set_session

router = APIRouter(prefix="/chat")
profile_store = JsonProfileStore()


def _serialize_message(*, role: str, content: str, message_type: str = "text") -> dict:
    return {
        "id": f"msg-{uuid4()}",
        "role": role,
        "content": content,
        "type": message_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/mode", response_model=ChatModeResponse)
async def chat_mode_followup(payload: ChatModeRequest) -> ChatModeResponse:
    session = get_session(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    # Prefer the new product_types key; fall back to categories (legacy)
    categories_payload = (
        session.get("product_types")
        or session.get("categories")
    )
    if not categories_payload:
        latest_response = session.get("latest_response") or {}
        categories_payload = (
            latest_response.get("product_types")
            or latest_response.get("categories")
        )

    if not categories_payload:
        raise HTTPException(status_code=400, detail="No recommendation context found for this session.")

    # ── Full context aggregation (Flow.md §8) ─────────────────────────────────
    original_query = session.get("original_query")
    clarification_answers = session.get("clarification_answers") or []
    session_category = session.get("session_category")

    profile_context = None
    user_id = session.get("user_id")
    if user_id:
        profile = profile_store.get(user_id)
        if profile:
            profile_context = profile.to_public_dict()

    answer = await answer_chat_followup(
        question=payload.user_message,
        categories_payload=categories_payload,
        profile_context=profile_context,
        original_query=original_query,
        clarification_answers=clarification_answers,
        session_category=session_category,
    )

    messages = list(session.get("messages") or [])
    messages.append(_serialize_message(role="user", content=payload.user_message, message_type="text"))
    messages.append(_serialize_message(role="assistant", content=answer, message_type="text"))

    set_session(
        payload.session_id,
        {
            **session,
            "messages": messages,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    return ChatModeResponse(session_id=payload.session_id, message=answer)
