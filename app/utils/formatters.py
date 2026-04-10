"""
Response formatting utilities.

Assembles final QueryResponse objects from ranked product data and
handles optional affiliate URL tag injection for all outbound product links.

Public API:
  build_recommendation_response()  — wraps ranked results in a QueryResponse.
  build_clarification_response()   — wraps a follow-up question in a QueryResponse.
"""

from app.models.responses import ProductTypeResult, ProductCard, QueryResponse


def build_recommendation_response(
    product_types: list[ProductTypeResult],
    session_id: str | None = None,
    summary: str | None = None,
    category: str | None = None,
) -> QueryResponse:
    """
    Assemble a successful recommendations response.

    Args:
        product_types: Product type results each with description + SERP items.
        session_id:    Active session ID, if any.
        summary:       AI reasoning text shown to the user above the product list.
        category:      Single session-level display label (Flow.md §21).

    Returns:
        QueryResponse with status='recommendations'.
    """
    return QueryResponse(
        status="recommendations",
        summary=summary,
        category=category,
        product_types=product_types,
        # Populate categories alias so old frontend normalizer still works
        categories=product_types,
        session_id=session_id,
    )


def build_clarification_response(
    message_or_follow_ups: str | list[str],
    session_id: str | None = None,
    clarification_round: int | None = None,
    asked_questions: int | None = None,
    max_total_questions: int | None = None,
    sufficiency_score: float | None = None,
) -> QueryResponse:
    """
    Assemble a clarification-needed response.

    Args:
        message_or_follow_ups: Either a clarification message string or list of follow-up questions.
        session_id: Active session ID, if any.

    Returns:
        QueryResponse with status='clarification_needed'.
    """
    if isinstance(message_or_follow_ups, str):
        # Single message string
        message = message_or_follow_ups
        questions = None
    else:
        # List of follow-up questions - join them into a message
        questions = message_or_follow_ups
        message = "\n".join([f"• {q}" for q in questions]) if questions else None
    
    return QueryResponse(
        status="clarification_needed",
        message=message,
        questions=questions,
        session_id=session_id,
        clarification_round=clarification_round,
        asked_questions=asked_questions,
        max_total_questions=max_total_questions,
        sufficiency_score=sufficiency_score,
    )


