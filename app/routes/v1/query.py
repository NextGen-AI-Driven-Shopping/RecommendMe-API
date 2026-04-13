"""
Query route handlers — main pipeline orchestrator (Steps 1-7 of Flow.md).

POST /v1/query
  Step 1: Receive query, validate
  Step 2: Classify (CLEAR / VAGUE / AMBIGUOUS / OUT_OF_SCOPE)
  Step 2.5: Pre-clarification question (if vague/ambiguous)
  Step 3: Follow-up Question Engine (Round 1: 3 questions, Round 2: 2 questions)
  Step 4: Auth gate check (pass-through for now)
  Step 5: Generate recommendation plan (AI) — category + product types
  Step 6: For each Product Type, fire SERP query — product items
  Step 7: Return response
"""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request

from app.core.exceptions import AIServiceException, ValidationException
from app.core.logger import get_logger
from app.models.internal import ProductType, QuestionWithOptions, RecommendationResult
from app.models.requests import QueryRequest
from app.models.responses import QueryResponse, ProductTypeResponse, ProductItemResponse
from app.services.clarification_runtime import (
    QuestionEngineError,
    generate_preclarification_question,
    generate_round1_questions,
    generate_round2_questions,
)
from app.services.products import fetch_product_items
from app.services.recommender import RecommendationServiceError, generate_recommendation_plan
from app.services.vagueness import classify_vagueness
from app.utils.formatters import (
    build_clarification_response,
    build_error_response,
    build_out_of_scope_response,
    build_preclarification_response,
    build_recommendation_response,
)
from app.utils.session import get_session, set_session
from app.utils.validators import sanitize_and_validate_query

logger = get_logger(__name__)
router = APIRouter()

MAX_TOTAL_QUESTIONS = 5
MAX_PRODUCT_TYPES = 10
MAX_ITEMS_PER_TYPE = 10
BUSY_MESSAGE = "Our recommendation engine is temporarily unavailable. Please try again in a moment."
REQUEST_DEDUP_TTL_SECONDS = 30.0


# ── Helpers ──────────────────────────────────────────────────────────────────


def _prune_request_cache(request_cache: dict[str, dict], now: float) -> None:
    stale_keys = [
        key for key, entry in request_cache.items()
        if not isinstance(entry, dict)
        or now - float(entry.get("timestamp", 0.0)) > REQUEST_DEDUP_TTL_SECONDS
    ]
    for key in stale_keys:
        request_cache.pop(key, None)


def _get_cached_response(request_cache: dict[str, dict], request_id: str) -> QueryResponse | None:
    entry = request_cache.get(request_id)
    if not isinstance(entry, dict):
        return None
    response_payload = entry.get("response")
    if not isinstance(response_payload, dict):
        return None
    try:
        return QueryResponse.model_validate(response_payload)
    except Exception:
        return None


def _serialize_message(
    *,
    role: str,
    content: str,
    message_type: str | None = None,
    questions: list | None = None,
    summary: str | None = None,
    category: str | None = None,
    product_types: list | None = None,
) -> dict:
    return {
        "id": f"msg-{uuid.uuid4()}",
        "role": role,
        "content": content,
        "type": message_type,
        "questions": questions,
        "summary": summary,
        "category": category,
        "product_types": product_types,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _store_session_snapshot(session_id: str, snapshot: dict) -> None:
    current = get_session(session_id) or {}
    set_session(
        session_id,
        {
            **current,
            **snapshot,
            "session_id": session_id,
            "created_at": current.get("created_at") or datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )


def _serialize_clarification_answers(answers) -> list[dict]:
    """Convert clarification answers into JSON-safe dict payloads."""
    normalized: list[dict] = []
    for answer in answers or []:
        if isinstance(answer, dict):
            normalized.append({
                "question": str(answer.get("question", "")).strip(),
                "answer": str(answer.get("answer", "")).strip(),
            })
        elif hasattr(answer, "model_dump"):
            dumped = answer.model_dump()
            normalized.append({
                "question": str(dumped.get("question", "")).strip(),
                "answer": str(dumped.get("answer", "")).strip(),
            })
        else:
            normalized.append({
                "question": str(getattr(answer, "question", "")).strip(),
                "answer": str(getattr(answer, "answer", "")).strip(),
            })
    return normalized


def _build_full_context_query(
    original_query: str,
    clarification_answers: list[dict[str, str]],
) -> str:
    """Build a consolidated query with all Q&A context for the AI."""
    if not clarification_answers:
        return original_query

    qa_text = "\n".join(
        f"Q: {a['question']}\nA: {a['answer']}" for a in clarification_answers
    )
    return f"{original_query}\n\nUser's clarification context:\n{qa_text}"


# ── Main Query Handler ───────────────────────────────────────────────────────


@router.post("/query", response_model=QueryResponse)
async def handle_query(payload: QueryRequest, request: Request) -> QueryResponse:
    """
    Process query through the full Flow.md pipeline.

    Steps 1-7 are executed based on the current state (determined by
    clarification_round and clarification answers).
    """
    # ── Step 1: Validate ──
    clean_query, is_valid, reason = sanitize_and_validate_query(payload.user_message)
    if not is_valid:
        raise ValidationException(detail=reason)

    request_id = payload.request_id or str(uuid.uuid4())
    request_cache = getattr(request.app.state, "request_cache", None)
    if not isinstance(request_cache, dict):
        request_cache = {}
        request.app.state.request_cache = request_cache

    now = time.time()
    _prune_request_cache(request_cache, now)
    cached_response = _get_cached_response(request_cache, request_id)
    if cached_response is not None:
        logger.info("Returning deduplicated response request_id=%s", request_id)
        return cached_response

    def _cache_and_return(response: QueryResponse) -> QueryResponse:
        request_cache[request_id] = {
            "timestamp": time.time(),
            "response": response.model_dump(),
        }
        return response

    session_id = payload.session_id or str(uuid.uuid4())
    serialized_answers = _serialize_clarification_answers(payload.clarification)
    conversation = payload.conversation_history or []

    existing_session = get_session(session_id) or {
        "session_id": session_id,
        "status": "new",
        "title": "New Chat",
        "messages": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    session_messages = list(existing_session.get("messages", []))

    # Store user message
    session_messages.append(
        _serialize_message(role="user", content=clean_query)
    )
    _store_session_snapshot(
        session_id,
        {
            **existing_session,
            "status": existing_session.get("status") or "new",
            "title": existing_session.get("title") or clean_query[:40] or "New Chat",
            "messages": session_messages,
            "original_query": existing_session.get("original_query") or clean_query,
        },
    )

    original_query = existing_session.get("original_query") or clean_query
    clarification_round = payload.clarification_round

    logger.info(
        "Processing query session_id=%s round=%s answers=%d query_len=%d",
        session_id, clarification_round, len(serialized_answers), len(clean_query),
    )

    # ── Determine pipeline stage ──

    # If we have 5 answers (Round 2 complete) → go directly to recommendations
    if len(serialized_answers) >= 5 or clarification_round == 2:
        return await _generate_recommendations(
            session_id=session_id,
            original_query=original_query,
            clarification_answers=serialized_answers,
            conversation=conversation,
            existing_session=existing_session,
            session_messages=session_messages,
            _cache_and_return=_cache_and_return,
        )

    # If we have 3 answers (Round 1 complete) → generate Round 2
    if len(serialized_answers) >= 3 or clarification_round == 1:
        return await _generate_round2(
            session_id=session_id,
            original_query=original_query,
            clarification_answers=serialized_answers,
            existing_session=existing_session,
            session_messages=session_messages,
            _cache_and_return=_cache_and_return,
        )

    # If we have a pre-clarification answer (clarification_round == 0 with answer) → generate Round 1
    if clarification_round == 0 and len(serialized_answers) >= 1:
        # Pre-clarification was answered, proceed to Round 1
        return await _generate_round1(
            session_id=session_id,
            query=original_query,
            existing_session=existing_session,
            session_messages=session_messages,
            _cache_and_return=_cache_and_return,
        )

    # ── Step 2: Classify ──
    try:
        vagueness_result = await classify_vagueness(clean_query)
    except Exception as exc:
        logger.error("Vagueness classification failed: %s", exc)
        raise AIServiceException(detail=BUSY_MESSAGE) from exc

    # OUT_OF_SCOPE → graceful decline
    if vagueness_result.is_out_of_scope:
        response = build_out_of_scope_response(
            message=vagueness_result.out_of_scope_message or BUSY_MESSAGE,
            session_id=session_id,
        )
        session_messages.append(
            _serialize_message(
                role="assistant",
                content=response.message or "",
                message_type="out_of_scope",
            )
        )
        _store_session_snapshot(session_id, {
            **existing_session,
            "status": "new",
            "messages": session_messages,
        })
        return _cache_and_return(response)

    # VAGUE / AMBIGUOUS → Step 2.5: Pre-clarification
    if vagueness_result.needs_preclarification:
        try:
            pre_question = await generate_preclarification_question(
                query=clean_query,
                classification=vagueness_result.classification.value,
            )
        except QuestionEngineError:
            # Fall through to Round 1 if pre-clarification fails
            logger.warning("Pre-clarification failed, proceeding directly to Round 1")
            return await _generate_round1(
                session_id=session_id,
                query=clean_query,
                existing_session=existing_session,
                session_messages=session_messages,
                _cache_and_return=_cache_and_return,
            )

        response = build_preclarification_response(
            question=pre_question,
            session_id=session_id,
        )
        session_messages.append(
            _serialize_message(
                role="assistant",
                content=pre_question.question,
                message_type="pre_clarification",
                questions=[{"question": pre_question.question, "options": pre_question.options}],
            )
        )
        _store_session_snapshot(session_id, {
            **existing_session,
            "status": "clarification_needed",
            "messages": session_messages,
            "original_query": clean_query,
            "clarification_round": 0,
            "clarification_answers": [],
        })
        return _cache_and_return(response)

    # CLEAR → Step 3: Generate Round 1 questions
    return await _generate_round1(
        session_id=session_id,
        query=clean_query,
        existing_session=existing_session,
        session_messages=session_messages,
        _cache_and_return=_cache_and_return,
    )


# ── Pipeline Sub-Steps ───────────────────────────────────────────────────────


async def _generate_round1(
    *,
    session_id: str,
    query: str,
    existing_session: dict,
    session_messages: list,
    _cache_and_return,
) -> QueryResponse:
    """Step 3 Round 1: Generate 3 follow-up questions with options."""
    try:
        result = await generate_round1_questions(query=query)
    except QuestionEngineError as exc:
        logger.error("Round 1 generation failed: %s", exc)
        raise AIServiceException(detail=BUSY_MESSAGE) from exc

    response = build_clarification_response(
        questions=result.questions,
        session_id=session_id,
        clarification_round=1,
        asked_questions=0,
        max_total_questions=MAX_TOTAL_QUESTIONS,
    )

    questions_data = [
        {"question": q.question, "options": q.options}
        for q in result.questions
    ]
    session_messages.append(
        _serialize_message(
            role="assistant",
            content=response.message or "",
            message_type="followup",
            questions=questions_data,
        )
    )
    _store_session_snapshot(session_id, {
        **existing_session,
        "status": "clarification_needed",
        "messages": session_messages,
        "original_query": query,
        "clarification_round": 1,
        "pending_questions": questions_data,
        "clarification_answers": [],
    })
    return _cache_and_return(response)


async def _generate_round2(
    *,
    session_id: str,
    original_query: str,
    clarification_answers: list[dict],
    existing_session: dict,
    session_messages: list,
    _cache_and_return,
) -> QueryResponse:
    """Step 3 Round 2: Generate 2 targeted follow-up questions based on Round 1 answers."""
    try:
        result = await generate_round2_questions(
            query=original_query,
            round1_qa_pairs=clarification_answers[:3],
        )
    except QuestionEngineError as exc:
        logger.error("Round 2 generation failed: %s", exc)
        # If Round 2 fails, proceed with what we have to recommendations
        return await _generate_recommendations(
            session_id=session_id,
            original_query=original_query,
            clarification_answers=clarification_answers,
            conversation=[],
            existing_session=existing_session,
            session_messages=session_messages,
            _cache_and_return=_cache_and_return,
        )

    response = build_clarification_response(
        questions=result.questions,
        session_id=session_id,
        clarification_round=2,
        asked_questions=3,
        max_total_questions=MAX_TOTAL_QUESTIONS,
    )

    questions_data = [
        {"question": q.question, "options": q.options}
        for q in result.questions
    ]
    session_messages.append(
        _serialize_message(
            role="assistant",
            content=response.message or "",
            message_type="followup",
            questions=questions_data,
        )
    )
    _store_session_snapshot(session_id, {
        **existing_session,
        "status": "clarification_needed",
        "messages": session_messages,
        "original_query": original_query,
        "clarification_round": 2,
        "pending_questions": questions_data,
        "clarification_answers": clarification_answers,
    })
    return _cache_and_return(response)


async def _generate_recommendations(
    *,
    session_id: str,
    original_query: str,
    clarification_answers: list[dict],
    conversation: list,
    existing_session: dict,
    session_messages: list,
    _cache_and_return,
) -> QueryResponse:
    """Steps 5-7: Generate recommendations + fetch SERP items."""

    # Step 5: AI generates category + product types
    full_query = _build_full_context_query(original_query, clarification_answers)

    try:
        plan = await generate_recommendation_plan(
            query=full_query,
            conversation_context=[
                {"role": str(m.get("role", "user")), "content": str(m.get("content", ""))}
                for m in (conversation or [])
                if isinstance(m, dict) and m.get("content")
            ] if conversation else None,
        )
    except RecommendationServiceError as exc:
        logger.error("Recommendation plan failed session_id=%s: %s", session_id, exc)
        raise AIServiceException(detail=BUSY_MESSAGE) from exc

    if not plan.product_types:
        raise AIServiceException(detail=BUSY_MESSAGE)

    # Step 6: For each Product Type, fire SERP query
    semaphore = asyncio.Semaphore(4)

    async def _fetch_for_type(pt: ProductType) -> ProductType:
        async with semaphore:
            try:
                items = await fetch_product_items(pt.product_type)
                pt.product_items = items
                pt.serp_error = False
            except Exception as exc:
                logger.error(
                    "SERP fetch failed for product_type=%s: %s",
                    pt.product_type, str(exc)[:120],
                )
                pt.serp_error = True
                pt.serp_error_message = f"Couldn't load live products for {pt.product_type}."
            return pt

    await asyncio.gather(
        *[_fetch_for_type(pt) for pt in plan.product_types],
        return_exceptions=True,
    )

    # Check if any product type has items
    if plan.all_serp_failed:
        logger.warning("All SERP queries failed for session_id=%s", session_id)
        # Still return the plan with descriptions (no items)
        # Fall through — the frontend will show description-only cards

    # Step 7: Build response
    response = build_recommendation_response(
        result=plan,
        session_id=session_id,
        summary=f"Here are my recommendations based on your requirements.",
    )

    # Serialize product_types for session storage
    pt_data = [
        {
            "product_type": pt.product_type,
            "description": pt.description,
            "product_items": [item.model_dump() for item in pt.product_items],
            "serp_error": pt.serp_error,
        }
        for pt in plan.product_types
    ]

    session_messages.append(
        _serialize_message(
            role="assistant",
            content=response.summary or "",
            message_type="recommendations",
            summary=response.summary,
            category=plan.category,
            product_types=pt_data,
        )
    )
    _store_session_snapshot(session_id, {
        **existing_session,
        "status": "recommendations",
        "messages": session_messages,
        "original_query": original_query,
        "clarification_answers": clarification_answers,
        "category": plan.category,
        "product_types": pt_data,
        "latest_response": response.model_dump(),
    })

    total_items = sum(len(pt.product_items) for pt in plan.product_types)
    logger.info(
        "Recommendations delivered session_id=%s category=%s types=%d items=%d",
        session_id, plan.category, len(plan.product_types), total_items,
    )

    return _cache_and_return(response)
