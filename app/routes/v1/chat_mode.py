"""Post-results chat mode route handlers (Step 8 of Flow.md)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from app.models.requests import ChatModeRequest
from app.models.responses import ChatModeResponse, ProductTypeResponse
from app.services.chat_mode import answer_chat_followup, filter_product_types_by_names
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


def _extract_raw_product_types(session: dict) -> list[dict]:
    return (
        session.get("product_types")
        or (session.get("latest_response") or {}).get("product_types")
        or []
    )


def _validate_product_types(raw: list[dict]) -> list[ProductTypeResponse] | None:
    if not raw:
        return None
    validated: list[ProductTypeResponse] = []
    for pt in raw:
        try:
            validated.append(
                ProductTypeResponse.model_validate(pt) if isinstance(pt, dict) else pt
            )
        except Exception:
            continue
    return validated if validated else None


@router.post("/mode", response_model=ChatModeResponse)
async def chat_mode_followup(payload: ChatModeRequest) -> ChatModeResponse:
    session = get_session(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    has_context = bool(
        session.get("product_types")
        or session.get("categories")
        or (session.get("latest_response") or {}).get("product_types")
        or (session.get("latest_response") or {}).get("categories")
    )
    if not has_context:
        raise HTTPException(
            status_code=400,
            detail="No recommendation context found for this session.",
        )

    profile_context = None
    user_id = session.get("user_id")
    if user_id:
        profile = profile_store.get(user_id)
        if profile:
            profile_context = profile.to_public_dict()

    answer_text, selected_names = await answer_chat_followup(
        question=payload.user_message,
        session_data=session,
        profile_context=profile_context,
    )

    messages = list(session.get("messages") or [])
    messages.append(
        _serialize_message(role="user", content=payload.user_message, message_type="text")
    )
    messages.append(
        _serialize_message(role="assistant", content=answer_text, message_type="text")
    )
    set_session(
        payload.session_id,
        {**session, "messages": messages, "updated_at": datetime.now(timezone.utc).isoformat()},
    )

    # Provider error → no cards
    if selected_names is None:
        return ChatModeResponse(
            session_id=payload.session_id,
            message=answer_text,
            product_types=None,
            category=None,
        )

    raw_product_types = _extract_raw_product_types(session)
    filtered_raw = filter_product_types_by_names(raw_product_types, selected_names)

    # AI picked specific items → flatten ALL matched items across all
    # categories into one ranked list, ordered by AI's selection order
    if selected_names:
        all_items: list[dict] = []
        for pt in filtered_raw:
            all_items.extend(pt.get("product_items") or [])

        def rank_key(item: dict) -> int:
            name = (item.get("product_name") or "").lower()
            for i, sel in enumerate(selected_names):
                if sel.lower() in name or name in sel.lower():
                    return i
            return 999

        all_items.sort(key=rank_key)
        filtered_raw = [{
            "product_type": "Top Picks",
            "description": "",
            "product_items": all_items,
        }]

    validated = _validate_product_types(filtered_raw)

    return ChatModeResponse(
        session_id=payload.session_id,
        message=answer_text,
        product_types=validated,
        category=session.get("category"),
    )