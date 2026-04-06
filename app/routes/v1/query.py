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
from app.models.responses import CategoryResult, ProductCard, QueryResponse, SufficiencyCheckResponse
from app.services.clarification import ClarificationPlanner
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
MAX_PRODUCTS_PER_CATEGORY = 10
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


def _rank_label(index: int, existing_label: str | None = None) -> str:
    if existing_label and existing_label.strip():
        return existing_label.strip()
    if index == 1:
        return "Best Choice"
    return f"Top {index}"


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


async def _build_category_products(
    *,
    category: str,
    query: str,
    product_plan: list,
    on_progress: Callable[[list[ProductCard]], None] | None = None,
) -> list[ProductCard]:
    cards: list[ProductCard] = []

    individual_plan = product_plan[:MAX_PRODUCTS_PER_CATEGORY]
    for planned in individual_plan:
        try:
            fetched = await fetch_products(category=category, query=planned.name)
        except Exception:
            continue
        if not fetched:
            continue
        card = fetched[0]
        card.explanation = planned.explanation
        card.label = _rank_label(len(cards) + 1, planned.label)
        cards.append(card)
        if on_progress is not None:
            on_progress(cards)
        if len(cards) >= MAX_PRODUCTS_PER_CATEGORY:
            return cards

    if len(product_plan) > MAX_PRODUCTS_PER_CATEGORY and len(cards) < MAX_PRODUCTS_PER_CATEGORY:
        grouped_query = ", ".join(p.name for p in product_plan[MAX_PRODUCTS_PER_CATEGORY:])
        grouped = await fetch_products(category=category, query=grouped_query)
        for fetched_card in grouped or []:
            if len(cards) >= MAX_PRODUCTS_PER_CATEGORY:
                break
            fetched_card.label = _rank_label(len(cards) + 1)
            cards.append(fetched_card)
            if on_progress is not None:
                on_progress(cards)

    if not cards:
        category_fallback, broad_fallback = await asyncio.gather(
            fetch_products(category=category, query=query),
            fetch_products(category="", query=query),
            return_exceptions=True,
        )
        fallback_lists: list[list[ProductCard]] = []
        for result in (category_fallback, broad_fallback):
            if isinstance(result, Exception) or not result:
                continue
            fallback_lists.append(result)

        for fallback_list in fallback_lists:
            for fallback_card in fallback_list:
                if len(cards) >= MAX_PRODUCTS_PER_CATEGORY:
                    break
                fallback_card.label = _rank_label(len(cards) + 1)
                cards.append(fallback_card)
                if on_progress is not None:
                    on_progress(cards)
            if len(cards) >= MAX_PRODUCTS_PER_CATEGORY:
                break

    if not cards and product_plan:
        for planned in product_plan[:3]:
            card = ProductCard(
                title=planned.name,
                url=f"https://www.google.com/search?q={planned.name.replace(' ', '+')}",
                explanation="Live listings unavailable. Search Google for alternatives.",
                label=_rank_label(len(cards) + 1, planned.label),
            )
            cards.append(card)
            if on_progress is not None:
                on_progress(cards)

    return cards


@router.post("/query", response_model=QueryResponse)
async def handle_query(payload: QueryRequest) -> QueryResponse:
    """Process query through vagueness analysis and recommendation pipeline."""
    clean_query, is_valid, reason = sanitize_and_validate_query(payload.user_message)
    if not is_valid:
        raise ValidationException(detail=reason)

    request_id = payload.request_id or str(uuid.uuid4())
    
    # Get the app state from globals (hack, but works for deduplication)
    # Check if we need access to app state - we'll need to pass it through
    # For now, log the request_id for backend tracking
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

    if payload.clarification:
        plan = clarification_planner.plan_next_step(
            clean_query,
            payload.clarification,
            max_total_questions=MAX_TOTAL_QUESTIONS,
        )
        asked_questions = plan["asked_questions"]
        next_question = plan["next_questions"][0] if plan["next_questions"] else None

        if not plan["sufficient"] and next_question:
            response = build_clarification_response(
                message_or_follow_ups=[next_question],
                session_id=session_id,
                clarification_round=plan["round"],
                asked_questions=asked_questions,
                max_total_questions=MAX_TOTAL_QUESTIONS,
                sufficiency_score=plan["sufficiency_score"],
            )
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
                            content=next_question,
                            message_type="followup",
                            questions=[next_question],
                        )
                    ],
                    "original_query": clean_query,
                    "pending_questions": [next_question],
                    "current_question_index": 0,
                    "clarification_answers": serialized_clarification_answers,
                    "latest_response": response.model_dump(),
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
            vagueness_result = await classify_vagueness(clean_query, allow_fallback=True)
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
            },
        )
        return response

    if vagueness_result.classification == "VAGUE":
        follow_ups = vagueness_result.follow_ups or clarification_planner.generate_initial_questions(
            clean_query,
            max_questions=1,
        )
        next_question = follow_ups[0] if follow_ups else None
        if not next_question:
            raise AIServiceException(detail=BUSY_MESSAGE)
        response = build_clarification_response(
            message_or_follow_ups=[next_question],
            session_id=session_id,
            clarification_round=1,
            asked_questions=0,
            max_total_questions=MAX_TOTAL_QUESTIONS,
            sufficiency_score=0.0,
        )
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
                            content=next_question,
                        message_type="followup",
                            questions=[next_question],
                    )
                ],
                "original_query": clean_query,
                    "pending_questions": [next_question],
                "current_question_index": 0,
                "clarification_answers": [],
                "latest_response": response.model_dump(),
            },
        )
        return response

    try:
        category_plan = await generate_category_plan(clean_query, context=conversation)
    except RecommendationServiceError as exc:
        logger.error("Category orchestration failed session_id=%s error=%s", session_id, exc)
        raise AIServiceException(detail=BUSY_MESSAGE) from exc

    category_results: list[CategoryResult] = []
    categories = category_plan.categories[:5] if category_plan.categories else ["Recommended Products"]

    def _persist_recommendation_progress(summary_text: str) -> None:
        categories_payload = [category.model_dump() for category in category_results]
        partial_response = build_recommendation_response(
            categories=category_results,
            session_id=session_id,
            summary=summary_text,
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
                "original_query": clean_query,
                "pending_questions": None,
                "current_question_index": None,
                "clarification_answers": serialized_clarification_answers,
                "latest_response": partial_response.model_dump(),
                "categories": categories_payload,
                "reasoning": category_plan.reasoning,
                "recommended_products": [p.name for p in category_plan.recommended_products],
            },
        )

    for category_name in categories:
        category_result = CategoryResult(
            category=category_name,
            tagline=f"Top picks for {category_name.lower()}",
            why_needed=f"{category_name} is essential based on your context, constraints, and intended usage.",
            products=[],
        )
        category_results.append(category_result)
        _persist_recommendation_progress(f"Working on {category_name}...")

        category_index = len(category_results) - 1

        def _on_product_progress(cards: list[ProductCard]) -> None:
            category_results[category_index].products = list(cards)
            _persist_recommendation_progress(f"Working on {category_name}...")

        try:
            product_cards = await _build_category_products(
                category=category_name,
                query=clean_query,
                product_plan=category_plan.recommended_products,
                on_progress=_on_product_progress,
            )

            if not product_cards:
                logger.warning("No live products for category=%s session_id=%s", category_name, session_id)
                category_results.pop()
                _persist_recommendation_progress("Continuing with the next category...")
                continue

            category_results[category_index].products = product_cards
            _persist_recommendation_progress(f"Completed {category_name}.")
        except Exception as e:
            # CRITICAL FIX: Handle individual category failures gracefully
            # Instead of failing the entire request, skip the category and continue
            logger.error(
                "Failed to fetch products for category=%s session_id=%s error=%s",
                category_name, session_id, str(e)
            )
            category_results.pop()
            _persist_recommendation_progress(f"Skipped {category_name} due to temporary issues. Continuing...")
            continue

    if not category_results:
        raise AIServiceException(
            detail="No live product listings could be fetched from SerpAPI. "
            "Please verify your SERPAPI_KEY or try again later. "
            "If the error persists, we may be temporarily unavailable."
        )

    response = build_recommendation_response(
        categories=category_results,
        session_id=session_id,
        summary=category_plan.reasoning,
    )
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
                    categories=[category.model_dump() for category in category_results],
                )
            ],
            "original_query": clean_query,
            "pending_questions": None,
            "current_question_index": None,
            "clarification_answers": serialized_clarification_answers,
            "latest_response": response.model_dump(),
            "categories": [category.model_dump() for category in category_results],
            "reasoning": category_plan.reasoning,
            "recommended_products": [p.name for p in category_plan.recommended_products],
        },
    )

    logger.info(
        "Returning recommendations session_id=%s categories=%d",
        session_id,
        len(category_results),
    )
    
    # CRITICAL FIX: Log request metrics for debugging and monitoring
    total_products = sum(len(cat.products) for cat in category_results) if category_results else 0
    logger.info(
        "REQUEST_METRICS request_id=%s session_id=%s "
        "categories=%d products=%d products_per_category=%.1f status=success",
        request_id,
        session_id,
        len(category_results),
        total_products,
        total_products / len(category_results) if category_results else 0
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
