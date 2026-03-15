"""Query route handler for `POST /v1/query`."""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.core.exceptions import AIServiceException, ValidationException
from app.core.logger import get_logger
from app.core.security import sanitize_input
from app.models.requests import QueryRequest
from app.models.responses import CategoryResult, ProductCard, QueryResponse
from app.services.products import fetch_products
from app.services.recommender import RecommendationServiceError, generate_category_plan
from app.services.vagueness import VaguenessResult, VaguenessServiceError, classify_vagueness
from app.utils.formatters import build_clarification_response, build_recommendation_response
from app.utils.session import set_session
from app.utils.validators import is_valid_query

logger = get_logger(__name__)
router = APIRouter()


def _build_fallback_questions(query: str) -> list[str]:
    """Generate default follow-up questions when provider questions are unavailable."""
    topic = query[:80].strip()
    return [
        f"What is your budget range for {topic}?",
        "Which brand or quality level do you prefer?",
        "What is your primary use case and timeline for this purchase?",
    ]


@router.post("/query", response_model=QueryResponse)
async def handle_query(
    payload: QueryRequest,
) -> QueryResponse:
    """Process user query through vagueness detection and provider fallback orchestration."""
    clean_query = sanitize_input(payload.user_message)
    is_valid, reason = is_valid_query(clean_query)
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

    # Step 1: Vagueness detection via providers
    if payload.clarification:
        vagueness_result = VaguenessResult(classification="CLEAR")
        clarification_text = "\n".join(
            f"Q: {c.question}\nA: {c.answer}" for c in payload.clarification
        )
        clean_query = f"{clean_query}\n\nUser Context:\n{clarification_text}"
        logger.info("Bypassing vagueness check due to provided clarifications.")
    else:
        try:
            vagueness_result = await classify_vagueness(clean_query, allow_fallback=True)
        except VaguenessServiceError as exc:
            logger.error("Vagueness classification failed session_id=%s error=%s", session_id, exc)
            raise AIServiceException(detail="All AI providers failed for vagueness classification.") from exc

    if vagueness_result.classification == "VAGUE":
        follow_ups = vagueness_result.follow_ups or _build_fallback_questions(clean_query)
        response = build_clarification_response(
            message_or_follow_ups=follow_ups[:3],
            session_id=session_id,
        )
        set_session(
            session_id,
            {
                "status": "clarification_needed",
                "query": clean_query,
                "follow_ups": follow_ups,
            },
        )
        return response

    # Step 2: Category + product reasoning via provider fallback
    # (Gemini -> GROQ -> OpenAI -> Ollama).
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
                "No live products for product=%s session_id=%s — using fallback",
                product_info.name,
                session_id,
            )
            # Create a Google search fallback
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
