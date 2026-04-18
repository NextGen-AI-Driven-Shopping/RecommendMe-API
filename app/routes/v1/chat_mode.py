"""Post-results chat mode route handlers (Step 8 of Flow.md)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import get_optional_user
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
async def chat_mode_followup(
    payload: ChatModeRequest,
    current=Depends(get_optional_user),
) -> ChatModeResponse:
    session = get_session(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    # Ownership check: if the session belongs to a user, the caller must be that user.
    session_user_id = session.get("user_id")
    if session_user_id:
        if not current:
            raise HTTPException(status_code=401, detail="Authentication required to access this session.")
        if current["user"].user_id != session_user_id:
            raise HTTPException(status_code=403, detail="Access denied.")

    # Verify recommendation context exists
    has_context = bool(
        session.get("product_types")
        or session.get("categories")
        or (session.get("latest_response") or {}).get("product_types")
        or (session.get("latest_response") or {}).get("categories")
    )
    if not has_context:
        raise HTTPException(status_code=400, detail="No recommendation context found for this session.")

    # Get user profile for personalization
    profile_context = None
    user_id = session.get("user_id")
    if user_id:
        profile = profile_store.get(user_id)
        if profile:
            profile_context = profile.to_public_dict()

    answer = await answer_chat_followup(
        question=payload.user_message,
        session_data=session,
        profile_context=profile_context,
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
