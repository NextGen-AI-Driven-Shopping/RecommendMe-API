"""Query route handlers for POST /v1/query and /v1/query/sufficiency_check."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Callable

from fastapi import APIRouter

from app.core.exceptions import AIServiceException, ValidationException
from app.core.logger import get_logger
from app.models.requests import QueryRequest, SufficiencyCheckRequest
from app.models.responses import ProductCard, ProductTypeResult, QueryResponse, SufficiencyCheckResponse
from app.services.clarification import ClarificationPlanner
from app.services.intent_engine import classify_intent
from app.services.products import fetch_products
from app.services.recommender import RecommendationServiceError, generate_category_plan
from app.services.vagueness import VaguenessResult, VaguenessServiceError, classify_vagueness
from app.utils.formatters import build_clarification_response, build_recommendation_response
from app.utils.session import get_session, set_session
from app.utils.validators import sanitize_and_validate_query

logger = get_logger(__name__)
router = APIRouter()
clarification_planner = ClarificationPlanner()
MAX_TOTAL_QUESTIONS = 5
MAX_PRODUCTS_PER_TYPE = 10
BUSY_MESSAGE = "All AI services are currently unavailable. Please try again later."


def _serialize_message(
    *,
    role: str,
    content: str,
    message_type: str | None = None,
    questions: list[str] | None = None,
    summary: str | None = None,
    categories: list | None = None,
) -> dict:
    return {
        "id": f"msg-{uuid.uuid4()}",
        "role": role,
        "content": content,
        "type": message_type,
        "questions": questions,
        "summary": summary,
        "categories": categories,
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


def _with_recommendation_message(
    messages: list[dict],
    *,
    summary: str,
    categories_payload: list[dict],
) -> list[dict]:
    """Append or replace the latest assistant recommendation message."""
    next_messages = list(messages)
    recommendation_message = _serialize_message(
        role="assistant",
        content=summary,
        message_type="recommendations",
        summary=summary,
        categories=categories_payload,
    )

    if (
        next_messages
        and next_messages[-1].get("role") == "assistant"
        and next_messages[-1].get("type") == "recommendations"
    ):
        recommendation_message["id"] = next_messages[-1].get("id", recommendation_message["id"])
        next_messages[-1] = recommendation_message
    else:
        next_messages.append(recommendation_message)

    return next_messages


def _serialize_clarification_answers(answers) -> list[dict]:
    """Convert clarification answers into JSON-safe dict payloads."""
    normalized: list[dict] = []
    for answer in answers or []:
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


async def _fetch_product_type_items(
    *,
    product_type: str,
    description: str,
    query: str,
    context_signals: str,
    api_calls_counter: list[int],
) -> ProductTypeResult:
    """
    Fetch SERP products for a single product type.

    Flow.md §6:
    - Query = Product Type + optional context signals (region, price range).
    - One SERP call per Product Type. No batching.
    - Return up to 10 items per Product Type.
    - Retry once per Product Type. If second attempt fails, fall back immediately.
    - Never block rendering — return ProductTypeResult with empty product_items on failure.
    """
    from app.services.system_state import MAX_API_CALLS

    serp_query = f"{product_type} {context_signals}".strip() if context_signals else product_type

    # Budget check
    if api_calls_counter[0] >= MAX_API_CALLS:
        logger.warning(
            "[RecommendMe] SERP fetch skipped — budget exhausted product_type=%r", product_type
        )
        return ProductTypeResult(
            product_type=product_type,
            description=description,
            product_items=[],
            serp_failed=True,
        )

    api_calls_counter[0] += 1

    # Attempt 1
    fetched = None
    try:
        fetched = await fetch_products(category=product_type, query=serp_query)
    except Exception as exc:
        logger.error(
            "[RecommendMe] SERP fetch failed — Product Type: %r\nReason: %s\nAttempt: 1 of 2\nFallback: Displaying AI-generated recommendation only.",
            product_type,
            str(exc)[:200],
        )

    # Attempt 2 (retry once per Flow.md §261)
    if not fetched:
        try:
            fetched = await fetch_products(category=product_type, query=serp_query)
        except Exception as exc:
            logger.error(
                "[RecommendMe] SERP fetch failed — Product Type: %r\nReason: %s\nAttempt: 2 of 2\nFallback: Displaying AI-generated recommendation only.",
                product_type,
                str(exc)[:200],
            )

    if not fetched:
        logger.warning(
            "[RecommendMe] SERP returned no products — Product Type: %r. Showing AI-generated recommendation only.",
            product_type,
        )
        return ProductTypeResult(
            product_type=product_type,
            description=description,
            product_items=[],
            serp_failed=True,
        )

    items = fetched[:MAX_PRODUCTS_PER_TYPE]
    logger.info(
        "[RecommendMe] SERP success — Product Type: %r  items: %d",
        product_type,
        len(items),
    )
    return ProductTypeResult(
        product_type=product_type,
        description=description,
        product_items=items,
        serp_failed=False,
    )


def _extract_context_signals(query: str, clarification_answers: list[dict]) -> str:
    """Build a short context signal string from clarification answers (region, price range, etc.)."""
    signals: list[str] = []
    for pair in clarification_answers:
        answer = str(pair.get("answer", "")).strip()
        if answer:
            signals.append(answer)
    # Keep signal string short — just enough to enrich the SERP query
    combined = " ".join(signals[:3])
    return combined[:120]


@router.post("/query", response_model=QueryResponse)
async def handle_query(payload: QueryRequest) -> QueryResponse:
    """Process query through vagueness analysis and recommendation pipeline."""
    clean_query, is_valid, reason = sanitize_and_validate_query(payload.user_message)
    if not is_valid:
        raise ValidationException(detail=reason)

    request_id = payload.request_id or str(uuid.uuid4())
    logger.info("Processing request request_id=%s", request_id)

    session_id = payload.session_id or str(uuid.uuid4())
    serialized_clarification_answers = _serialize_clarification_answers(payload.clarification)
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
    session_messages.append(
        _serialize_message(
            role="user",
            content=clean_query,
        )
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

    logger.info(
        "Processing query session_id=%s query_length=%d conversation_messages=%d",
        session_id,
        len(clean_query),
        len(conversation),
    )

    # ── Intent engine (fast, local, no AI call) ────────────────────────────
    intent_result = classify_intent(clean_query)
    domain_hint = intent_result.domain
    detected_intent = intent_result.intent
    logger.info(
        "Intent detected session_id=%s domain=%s intent=%s confidence=%.2f",
        session_id, domain_hint, detected_intent, intent_result.confidence,
    )

    if payload.clarification:
        plan = clarification_planner.plan_next_step(
            clean_query,
            payload.clarification,
            max_total_questions=MAX_TOTAL_QUESTIONS,
        )
        asked_questions = plan["asked_questions"]
        next_questions = plan["next_questions"] if plan["next_questions"] else []

        if not plan["sufficient"] and next_questions:
            # Return ONLY the first of the next questions (one at a time flow)
            first_next_question_only = [next_questions[0]]

            response = build_clarification_response(
                message_or_follow_ups=first_next_question_only,
                session_id=session_id,
                clarification_round=plan["round"],
                asked_questions=asked_questions,
                max_total_questions=MAX_TOTAL_QUESTIONS,
                sufficiency_score=plan["sufficiency_score"],
            )
            response.domain = domain_hint
            response.intent = detected_intent
            _store_session_snapshot(
                session_id,
                {
                    **existing_session,
                    "status": "clarification_needed",
                    "title": existing_session.get("title") or clean_query[:40] or "New Chat",
                    "messages": session_messages
                    + [
                        _serialize_message(
                            role="assistant",
                            content=next_questions[0],
                            message_type="followup",
                            questions=first_next_question_only,
                        )
                    ],
                    "original_query": clean_query,
                    "pending_questions": next_questions,
                    "current_question_index": 0,
                    "clarification_answers": serialized_clarification_answers,
                    "latest_response": response.model_dump(),
                    "domain": domain_hint,
                    "intent": detected_intent,
                },
            )
            return response

        vagueness_result = VaguenessResult(classification="CLEAR")
        clarification_text = "\n".join(
            f"Q: {c.question}\nA: {c.answer}" for c in payload.clarification
        )
        clean_query = f"{clean_query}\n\nUser Context:\n{clarification_text}"
        logger.info("Bypassing vagueness check due to sufficient clarifications.")
    else:
        try:
            vagueness_result = await classify_vagueness(
                clean_query, allow_fallback=True, domain_hint=domain_hint
            )
        except VaguenessServiceError as exc:
            logger.error("Vagueness classification failed session_id=%s error=%s", session_id, exc)
            raise AIServiceException(detail=BUSY_MESSAGE) from exc

    if vagueness_result.classification == "RETRY":
        response = build_clarification_response(
            message_or_follow_ups=vagueness_result.retry_message,
            session_id=session_id,
            clarification_round=1,
            asked_questions=0,
            max_total_questions=MAX_TOTAL_QUESTIONS,
            sufficiency_score=0.0,
        )
        response.domain = domain_hint
        response.intent = detected_intent
        retry_text = vagueness_result.retry_message or "I couldn't process that request right now. Please try again."
        _store_session_snapshot(
            session_id,
            {
                **existing_session,
                "status": "clarification_needed",
                "title": existing_session.get("title") or clean_query[:40] or "New Chat",
                "messages": session_messages
                + [
                    _serialize_message(
                        role="assistant",
                        content=retry_text,
                        message_type="followup",
                        questions=[retry_text],
                    )
                ],
                "original_query": clean_query,
                "pending_questions": [retry_text],
                "current_question_index": 0,
                "clarification_answers": serialized_clarification_answers,
                "latest_response": response.model_dump(),
                "domain": domain_hint,
                "intent": detected_intent,
            },
        )
        return response

    if vagueness_result.classification == "VAGUE":
        follow_ups = vagueness_result.follow_ups or clarification_planner.generate_initial_questions(
            clean_query,
            max_questions=3,
        )
        if not follow_ups:
            raise AIServiceException(detail=BUSY_MESSAGE)

        # Return ONLY the first question (one at a time flow)
        first_question_only = [follow_ups[0]]

        response = build_clarification_response(
            message_or_follow_ups=first_question_only,
            session_id=session_id,
            clarification_round=1,
            asked_questions=0,
            max_total_questions=MAX_TOTAL_QUESTIONS,
            sufficiency_score=0.0,
        )
        response.domain = domain_hint
        response.intent = detected_intent
        _store_session_snapshot(
            session_id,
            {
                **existing_session,
                "status": "clarification_needed",
                "title": existing_session.get("title") or clean_query[:40] or "New Chat",
                "messages": session_messages
                + [
                    _serialize_message(
                        role="assistant",
                        content=follow_ups[0],
                        message_type="followup",
                        questions=first_question_only,
                    )
                ],
                "original_query": clean_query,
                "pending_questions": follow_ups,
                "current_question_index": 0,
                "clarification_answers": [],
                "latest_response": response.model_dump(),
                "domain": domain_hint,
                "intent": detected_intent,
            },
        )
        return response

    # ── Step 5: AI generates category + product types ───────────────────────
    try:
        category_plan = await generate_category_plan(
            clean_query, context=conversation, domain_hint=domain_hint
        )
    except RecommendationServiceError as exc:
        logger.error("Category orchestration failed session_id=%s error=%s", session_id, exc)
        raise AIServiceException(detail=BUSY_MESSAGE) from exc

    category_label = category_plan.category
    product_type_infos = category_plan.product_types[:10]  # Flow.md: max 10

    # Build context signals from clarification answers for SERP enrichment
    context_signals = _extract_context_signals(clean_query, serialized_clarification_answers)

    # ── Step 6: Per-product-type SERP calls ──────────────────────────────────
    # Flow.md: One SERP call per Product Type. Retry once. Never block rendering.
    product_type_results: list[ProductTypeResult] = []
    api_calls_counter: list[int] = [0]

    def _persist_progress(summary_text: str) -> None:
        categories_payload = [r.model_dump() for r in product_type_results]
        partial_response = build_recommendation_response(
            product_types=product_type_results,
            session_id=session_id,
            summary=summary_text,
            category=category_label,
        )
        _store_session_snapshot(
            session_id,
            {
                **existing_session,
                "status": "recommendations",
                "title": existing_session.get("title") or clean_query[:40] or "New Chat",
                "messages": _with_recommendation_message(
                    session_messages,
                    summary=summary_text,
                    categories_payload=categories_payload,
                ),
                "original_query": existing_session.get("original_query") or clean_query,
                "pending_questions": None,
                "current_question_index": None,
                "clarification_answers": serialized_clarification_answers,
                "latest_response": partial_response.model_dump(),
                # Store full structure for chat mode context (Flow.md §8)
                "session_category": category_label,
                "product_types": categories_payload,
                "categories": categories_payload,
                "reasoning": category_plan.reasoning,
            },
        )

    for pt_info in product_type_infos:
        _persist_progress(f"Searching for {pt_info.product_type}…")
        result = await _fetch_product_type_items(
            product_type=pt_info.product_type,
            description=pt_info.description,
            query=clean_query,
            context_signals=context_signals,
            api_calls_counter=api_calls_counter,
        )
        product_type_results.append(result)
        _persist_progress(
            f"Found {len(result.product_items)} items for {pt_info.product_type}."
            if not result.serp_failed
            else f"Live data unavailable for {pt_info.product_type} — showing AI recommendation."
        )

    # ── Build final response ─────────────────────────────────────────────────
    all_items = [card for pt in product_type_results for card in pt.product_items]
    all_serp_failed = all(pt.serp_failed for pt in product_type_results)

    if not product_type_results:
        # No product types at all — full degraded response
        logger.warning("All product types failed session_id=%s", session_id)
        fallback_types = [
            ProductTypeResult(
                product_type=pt.product_type,
                description=pt.description,
                product_items=[],
                serp_failed=True,
            )
            for pt in product_type_infos
        ]
        degraded_response = QueryResponse(
            status="recommendations",
            session_id=session_id,
            summary=(
                "Live product listings are temporarily unavailable. "
                "The AI summary above describes what to look for."
            ),
            category=category_label,
            product_types=fallback_types,
            categories=fallback_types,
            data_source="unavailable",
            degraded=True,
            domain=domain_hint,
            intent=detected_intent,
        )
        return degraded_response

    all_prices_none = all(card.price is None for card in all_items) if all_items else True
    if all_serp_failed or (all_prices_none and not all_items):
        data_source_value = "llm_only"
        is_degraded = True
    elif all_prices_none:
        data_source_value = "llm_only"
        is_degraded = True
    else:
        data_source_value = "live"
        is_degraded = False

    response = build_recommendation_response(
        product_types=product_type_results,
        session_id=session_id,
        summary=category_plan.reasoning,
        category=category_label,
    )
    response.domain = domain_hint
    response.intent = detected_intent
    response.data_source = data_source_value   # type: ignore[assignment]
    response.degraded = is_degraded

    categories_payload = [r.model_dump() for r in product_type_results]
    _store_session_snapshot(
        session_id,
        {
            **existing_session,
            "status": "recommendations",
            "title": existing_session.get("title") or clean_query[:40] or "New Chat",
            "messages": session_messages
            + [
                _serialize_message(
                    role="assistant",
                    content=category_plan.reasoning,
                    message_type="recommendations",
                    summary=category_plan.reasoning,
                    categories=categories_payload,
                )
            ],
            "original_query": existing_session.get("original_query") or clean_query,
            "pending_questions": None,
            "current_question_index": None,
            "clarification_answers": serialized_clarification_answers,
            "latest_response": response.model_dump(),
            # Full context for chat mode (Flow.md §8)
            "session_category": category_label,
            "product_types": categories_payload,
            "categories": categories_payload,
            "reasoning": category_plan.reasoning,
        },
    )

    total_products = sum(len(pt.product_items) for pt in product_type_results)
    logger.info(
        "REQUEST_METRICS request_id=%s session_id=%s "
        "category=%r product_types=%d products=%d data_source=%s status=success",
        request_id,
        session_id,
        category_label,
        len(product_type_results),
        total_products,
        data_source_value,
    )
    return response


@router.post("/query/sufficiency_check", response_model=SufficiencyCheckResponse)
async def sufficiency_check(payload: SufficiencyCheckRequest) -> SufficiencyCheckResponse:
    """Evaluate if clarification answers are sufficient or more questions are needed."""
    clean_query, is_valid, reason = sanitize_and_validate_query(payload.user_message)
    if not is_valid:
        raise ValidationException(detail=reason)

    plan = clarification_planner.plan_next_step(
        clean_query,
        payload.clarification,
        max_total_questions=payload.max_total_questions,
    )

    return SufficiencyCheckResponse(
        sufficient=plan["sufficient"],
        score=plan["sufficiency_score"],
        asked_questions=plan["asked_questions"],
        max_total_questions=payload.max_total_questions,
        next_questions=plan["next_questions"],
        clarification_round=plan["round"],
    )
