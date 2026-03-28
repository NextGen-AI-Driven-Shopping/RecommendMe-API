"""Query route handlers for POST /v1/query and /v1/query/sufficiency_check."""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.core.exceptions import AIServiceException, ValidationException
from app.core.logger import get_logger
from app.models.requests import QueryRequest, SufficiencyCheckRequest
from app.models.responses import (
    CategoryResult,
    ProductCard,
    QueryResponse,
    SufficiencyCheckResponse,
)
from app.services.clarification import ClarificationPlanner
from app.services.products import fetch_products
from app.services.recommender import RecommendationServiceError, generate_category_plan
from app.services.vagueness import VaguenessResult, VaguenessServiceError, classify_vagueness
from app.utils.formatters import build_clarification_response, build_recommendation_response
from app.utils.session import set_session
from app.utils.validators import sanitize_and_validate_query

logger = get_logger(__name__)
router = APIRouter()
clarification_planner = ClarificationPlanner()
MAX_TOTAL_QUESTIONS = 5


@router.post("/query", response_model=QueryResponse)
async def handle_query(payload: QueryRequest) -> QueryResponse:
    """Process query through vagueness analysis and recommendation pipeline."""
    clean_query, is_valid, reason = sanitize_and_validate_query(payload.user_message)
    if not is_valid:
        raise ValidationException(detail=reason)

    session_id = payload.session_id or str(uuid.uuid4())
    conversation = payload.conversation_history or []

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

        if not plan["sufficient"] and plan["next_questions"]:
            response = build_clarification_response(
                message_or_follow_ups=plan["next_questions"],
                session_id=session_id,
                clarification_round=plan["round"],
                asked_questions=asked_questions,
                max_total_questions=MAX_TOTAL_QUESTIONS,
                sufficiency_score=plan["sufficiency_score"],
            )
            set_session(
                session_id,
                {
                    "status": "clarification_needed",
                    "query": clean_query,
                    "follow_ups": plan["next_questions"],
                    "clarification_round": plan["round"],
                    "asked_questions": asked_questions,
                    "sufficiency_score": plan["sufficiency_score"],
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
            raise AIServiceException(detail="All AI providers failed for vagueness classification.") from exc

    if vagueness_result.classification == "RETRY":
        return build_clarification_response(
            message_or_follow_ups=vagueness_result.retry_message,
            session_id=session_id,
            clarification_round=1,
            asked_questions=0,
            max_total_questions=MAX_TOTAL_QUESTIONS,
            sufficiency_score=0.0,
        )

    if vagueness_result.classification == "VAGUE":
        follow_ups = vagueness_result.follow_ups or clarification_planner.generate_initial_questions(
            clean_query,
            max_questions=3,
        )
        response = build_clarification_response(
            message_or_follow_ups=follow_ups[:5],
            session_id=session_id,
            clarification_round=1,
            asked_questions=0,
            max_total_questions=MAX_TOTAL_QUESTIONS,
            sufficiency_score=0.0,
        )
        set_session(
            session_id,
            {
                "status": "clarification_needed",
                "query": clean_query,
                "follow_ups": follow_ups,
                "clarification_round": 1,
                "asked_questions": 0,
            },
        )
        return response

    try:
        category_plan = await generate_category_plan(clean_query, context=conversation)
    except RecommendationServiceError as exc:
        logger.error("Category orchestration failed session_id=%s error=%s", session_id, exc)
        raise AIServiceException(detail="All AI providers failed for category reasoning.") from exc

    category_results: list[CategoryResult] = []
    main_category = category_plan.categories[0] if category_plan.categories else "Recommended Products"
    logger.info("AI recommended %d products for category=%s", len(category_plan.recommended_products), main_category)
    product_cards: list[ProductCard] = []

    for product_info in category_plan.recommended_products:
        fetched = await fetch_products(category="", query=product_info.name)
        if fetched:
            card = fetched[0]
            card.explanation = product_info.explanation
            card.label = product_info.label
            product_cards.append(card)
        else:
            logger.warning(
                "No live products for product=%s session_id=%s - using fallback",
                product_info.name,
                session_id,
            )
            fallback_card = ProductCard(
                title=product_info.name,
                url=f"https://www.google.com/search?q={product_info.name.replace(' ', '+')}",
                explanation="Live listings unavailable. Search Google for alternatives.",
                label=product_info.label,
            )
            product_cards.append(fallback_card)

    if product_cards:
        category_results.append(CategoryResult(category=main_category, products=product_cards))

    if not category_results:
        raise AIServiceException(
            detail="No live product listings could be fetched from SerpAPI. "
            "Please verify your SERPAPI_KEY or try again later."
        )

    response = build_recommendation_response(
        categories=category_results,
        session_id=session_id,
        summary=category_plan.reasoning,
    )
    set_session(
        session_id,
        {
            "status": "recommendations",
            "query": clean_query,
            "categories": category_plan.categories,
            "reasoning": category_plan.reasoning,
            "recommended_products": [p.name for p in category_plan.recommended_products],
        },
    )

    logger.info(
        "Returning recommendations session_id=%s categories=%d",
        session_id,
        len(category_results),
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
