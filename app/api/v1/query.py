"""
Query route handler — POST /v1/query.

Core recommendation endpoint.  Accepts a user query with optional
conversation history, runs vagueness detection, and returns either
ranked product recommendations or a clarification prompt.

Pipeline (each step is wrapped in a safe fallback so incomplete
service implementations do not crash the API):

  1. Sanitise and validate the raw query string.
  2. Classify query vagueness (Tier 1 AI — Ollama / GPT-4o-mini).
  3. If the query is VAGUE, return a clarification prompt early.
  4. Extract structured intent and search categories (Tier 2 AI — GPT-4o).
  5. Fetch raw products from SerpAPI per category.
  6. Rank and score products (GPT-4o).
  7. Build and return the final QueryResponse.

Steps 4–6 return placeholder data while the respective service
implementations are being completed by the team.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_session
from app.core.exceptions import AIServiceException, ValidationException
from app.core.logger import get_logger
from app.core.security import sanitize_input
from app.models.requests import QueryRequest
from app.models.responses import CategoryResult, ProductCard, QueryResponse
from app.utils.formatters import build_clarification_response, build_recommendation_response
from app.utils.validators import is_valid_query

logger = get_logger(__name__)
router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def handle_query(
    payload: QueryRequest,
    session: dict = Depends(get_session),
) -> QueryResponse:
    """
    Process a product recommendation query.

    Returns a QueryResponse whose `status` is either:
      - "recommendations"     — with a list of ranked CategoryResult objects.
      - "clarification_needed" — with a follow-up question for the user.
    """
    # ------------------------------------------------------------------ #
    # DEBUG — log every incoming request immediately, before any processing,
    # so we can see what the frontend sent even if the handler crashes later.
    # ------------------------------------------------------------------ #
    print("\n" + "=" * 60)
    print("[QUERY ENDPOINT HIT]")
    print("Incoming Payload:")
    print(f"  session_id          = {payload.session_id!r}")
    print(f"  user_message        = {payload.user_message!r}")
    conv_len = len(payload.conversation_history) if payload.conversation_history else 0
    print(f"  conversation_history = {conv_len} message(s)")
    print("=" * 60)

    # ------------------------------------------------------------------ #
    # Step 1 — Sanitise and validate input
    # ------------------------------------------------------------------ #
    clean_query = sanitize_input(payload.user_message)
    valid, reason = is_valid_query(clean_query)
    if not valid:
        print(f"[QUERY] Validation failed: {reason}")
        logger.warning(f"Query validation failed: {reason}")
        raise ValidationException(detail=reason)

    # Resolve or create a session ID for conversation continuity.
    session_id = payload.session_id or str(uuid.uuid4())
    conversation = payload.conversation_history or []

    print(f"[QUERY] Processing request — session_id={session_id}")
    logger.info(f"Processing query session_id={session_id} query_length={len(clean_query)}")

    # ------------------------------------------------------------------ #
    # Step 2 — Vagueness classification (Tier 1 AI)
    # ------------------------------------------------------------------ #
    try:
        from app.services.vagueness import VaguenessServiceError, classify_vagueness

        vagueness_result = await classify_vagueness(clean_query, allow_fallback=True)
        classification = vagueness_result.classification
        follow_ups = vagueness_result.follow_ups or []
    except Exception as exc:
        # If the classification service is down, default to CLEAR so users
        # still receive recommendations rather than a hard failure.
        logger.warning(f"Vagueness check failed, defaulting to CLEAR: {exc!r}")
        classification = "CLEAR"
        follow_ups = []

    # ------------------------------------------------------------------ #
    # Step 3 — Return clarification prompt for vague queries
    # ------------------------------------------------------------------ #
    if classification == "VAGUE":
        follow_up_question = (
            follow_ups[0]
            if follow_ups
            else "Could you provide more details about what you're looking for?"
        )
        print(f"[QUERY] Classification: VAGUE — returning clarification prompt")
        logger.info(f"Query classified as VAGUE session_id={session_id}")
        response = build_clarification_response(
            follow_up=follow_up_question,
            session_id=session_id,
        )
        print("[QUERY] Returning response:")
        print(f"  status  = {response.status!r}")
        print(f"  message = {response.message!r}")
        print("=" * 60 + "\n")
        return response

    # ------------------------------------------------------------------ #
    # Step 4 — Intent extraction (Tier 2 AI — GPT-4o)
    # TODO: Full implementation pending from recommender service owner.
    # ------------------------------------------------------------------ #
    categories: list[str] = []
    try:
        from app.services.recommender import extract_intent

        intent = await extract_intent(clean_query, context=conversation)
        if intent is not None:
            categories = intent.categories
    except Exception as exc:
        # Temporary placeholder until intent extraction is completed.
        logger.warning(f"Intent extraction failed, continuing without categories: {exc!r}")

    # Fall back to a single category derived from the raw query when the
    # intent service has not yet been implemented.
    if not categories:
        categories = [clean_query]

    # ------------------------------------------------------------------ #
    # Step 5 — Product fetch per category (SerpAPI)
    # TODO: Full implementation pending from products service owner.
    # ------------------------------------------------------------------ #
    all_category_results: list[CategoryResult] = []

    for category in categories:
        try:
            from app.services.products import fetch_products

            raw_products = await fetch_products(category=category, query=clean_query)

            # fetch_products returns None while pending — treat as empty list.
            if raw_products is None:
                raise NotImplementedError("fetch_products not yet implemented")

            all_category_results.append(
                CategoryResult(category=category, products=raw_products)
            )
        except Exception as exc:
            # Temporary placeholder — return an empty category card so the
            # response structure is still valid.
            logger.warning(f"Product fetch failed for category '{category}': {exc!r}")
            all_category_results.append(
                CategoryResult(
                    category=category,
                    products=[
                        ProductCard(
                            title="Results coming soon",
                            url="#",
                            explanation=(
                                "Product search is being integrated. "
                                "Check back shortly."
                            ),
                        )
                    ],
                )
            )

    # ------------------------------------------------------------------ #
    # Step 6 — Ranking and explanation generation (GPT-4o)
    # TODO: Full ranking pipeline integration pending.
    # The RankingService is implemented but not yet wired into the async
    # route.  A synchronous stub is used here in the interim.
    # ------------------------------------------------------------------ #
    # Ranking is skipped for now; products are returned in fetch order.

    # ------------------------------------------------------------------ #
    # Step 7 — Build and return the final response
    # ------------------------------------------------------------------ #
    print(f"[QUERY] Classification: CLEAR — returning {len(all_category_results)} category result(s)")
    logger.info(
        f"Returning {len(all_category_results)} category result(s) "
        f"session_id={session_id}"
    )
    response = build_recommendation_response(
        categories=all_category_results,
        session_id=session_id,
    )
    print("[QUERY] Returning response:")
    print(f"  status     = {response.status!r}")
    print(f"  categories = {[c.category for c in (response.categories or [])]}")
    print(f"  session_id = {response.session_id!r}")
    print("=" * 60 + "\n")
    return response
