"""Query route handler for `POST /v1/query` with conversation memory."""

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
from app.utils.session import delete_session, get_session, set_session
from app.utils.validators import is_valid_query

logger = get_logger(__name__)
router = APIRouter()

def _safe_get(item, key: str, default=None):
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)

def _build_fallback_questions(query: str) -> list[str]:
    """Generate default follow-up questions when provider questions are unavailable."""
    topic = query[:80].strip()
    lower_topic = topic.lower()

    if "trek" in lower_topic or "hiking" in lower_topic or "camp" in lower_topic:
        return [
            "What specific trekking product do you need first, like shoes, backpack, jacket, or tent?",
            f"What budget range should I target for {topic}?",
            "Which features matter most to you, such as waterproofing, weight, durability, or size?",
        ]

    if any(term in lower_topic for term in ("beach", "vacation", "holiday", "trip", "travel", "bali")):
        return [
            "What exact product do you need for this trip, like clothes, sandals, sunscreen, luggage, or beach accessories?",
            f"What budget range should I target for {topic}?",
            "Which preferences matter most, such as waterproofing, comfort, compact size, style, or brand?",
        ]

    return [
        f"What exact product are you looking for related to {topic}?",
        f"What is your budget range for {topic}?",
        "Which features or preferences matter most, such as brand, size, durability, or style?",
    ]


def _merge_clarification_context(clean_query: str, clarification: list | None) -> str:
    if not clarification:
        return clean_query

    details: list[str] = []
    for item in clarification:
        answer = _safe_get(item, "answer", "")
        if answer:
            details.append(str(answer).strip())

    if not details:
        return clean_query

    return f"{clean_query}. User preferences: {'; '.join(details)}"


def _clarification_pairs(questions: list[str], answers: list[str]) -> list[dict[str, str]]:
    return [
        {"question": question, "answer": answer}
        for question, answer in zip(questions, answers)
        if question and answer
    ]

@router.post("/query", response_model=QueryResponse)
async def handle_query(payload: QueryRequest) -> QueryResponse:
    """Process query through vagueness detection and provider fallback with history."""
    
    # 1. Sanitize and Validate
    clean_query = sanitize_input(payload.user_message)
    is_valid, reason = is_valid_query(clean_query)
    if not is_valid:
        raise ValidationException(detail=reason)

    session_id = payload.session_id or str(uuid.uuid4())
    session_state = get_session(session_id) or {}
    
    # 2. Extract History (The Memory)
    # We pass this to the services so the AI knows the context
    conversation = payload.conversation_history or []
    stored_original_query = session_state.get("original_query")
    stored_questions = session_state.get("questions", [])
    stored_answers = session_state.get("answers", [])
    current_clarification = payload.clarification or []

    if session_state.get("status") == "clarifying" and not current_clarification:
        stored_answers = [*stored_answers, clean_query]
        if len(stored_answers) < len(stored_questions):
            set_session(
                session_id,
                {
                    "status": "clarifying",
                    "original_query": stored_original_query or clean_query,
                    "questions": stored_questions,
                    "answers": stored_answers,
                },
            )
            next_question = stored_questions[len(stored_answers)]
            return build_clarification_response(next_question, session_id=session_id)

        current_clarification = _clarification_pairs(stored_questions, stored_answers)
        clean_query = stored_original_query or clean_query
        delete_session(session_id)

    enriched_query = _merge_clarification_context(clean_query, current_clarification)

    logger.info(
        "Processing query session_id=%s query_length=%d conversation_depth=%d",
        session_id, len(clean_query), len(conversation),
    )

    if current_clarification:
        vagueness_result = VaguenessResult(classification="CLEAR", provider="ClarificationAnswers")
    else:
        # Step 1: Vagueness detection (Now context-aware)
        try:
            # We pass conversation history here so if the user answers a follow-up, 
            # the AI knows it's no longer vague.
            vagueness_result = await classify_vagueness(
                clean_query, 
                history=conversation, 
                allow_fallback=True
            )
        except VaguenessServiceError as exc:
            logger.error("Vagueness check failed session_id=%s", session_id)
            raise AIServiceException(detail="AI service unavailable for classification.") from exc

    if vagueness_result.classification == "VAGUE":
        follow_ups = vagueness_result.follow_ups or _build_fallback_questions(clean_query)
        set_session(
            session_id,
            {
                "status": "clarifying",
                "original_query": clean_query,
                "questions": follow_ups,
                "answers": [],
            },
        )
        return build_clarification_response(
            message_or_follow_ups=follow_ups[0],
            session_id=session_id,
        )

    # Step 2: Recommendation Reasoning (Using History)
    try:
        # Crucial: Passing 'context=conversation' so Groq/Gemini remembers previous picks
        category_plan = await generate_category_plan(enriched_query, context=conversation)
    except RecommendationServiceError as exc:
        logger.error("Recommendation failed session_id=%s", session_id)
        raise AIServiceException(detail="AI providers failed for reasoning.") from exc

    # Step 3: Product Fetching (Existing logic)
    category_results: list[CategoryResult] = []
    product_cards: list[ProductCard] = []
    categories = _safe_get(category_plan, "categories", []) or []
    reasoning = _safe_get(category_plan, "reasoning", "") or _safe_get(category_plan, "summary", "")
    recommended_products = _safe_get(category_plan, "recommended_products", []) or []

    for product_info in recommended_products:
        product_name = _safe_get(product_info, "name", "") or enriched_query
        product_explanation = _safe_get(product_info, "explanation", "Recommended based on your request.")
        product_label = _safe_get(product_info, "label", "Recommended")

        fetched = await fetch_products(category=categories[0] if categories else "", query=product_name)
        if fetched:
            card = fetched[0].model_copy(update={"explanation": product_explanation, "label": product_label})
            product_cards.append(card)
        else:
            # Fallback to a search link if SerpAPI fails for a specific item
            product_cards.append(ProductCard(
                title=product_name,
                price="Check Price",
                url=f"https://www.google.com/search?q={product_name.replace(' ', '+')}",
                rating=4.0,
                reviews=None,
                source="Google Search",
                explanation=f"{product_explanation} (Live listings unavailable right now.)",
                label=product_label,
            ))

    if product_cards:
        category_results.append(CategoryResult(
            category=categories[0] if categories else "Top Picks",
            products=product_cards
        ))

    # Step 4: Final Response
    return build_recommendation_response(
        categories=category_results,
        session_id=session_id,
        summary=reasoning,
    )
