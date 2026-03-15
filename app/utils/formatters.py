"""
Response formatting utilities.

Assembles final QueryResponse objects from ranked product data and
handles optional affiliate URL tag injection for all outbound product links.

Public API:
  build_recommendation_response()  — wraps ranked results in a QueryResponse.
  build_clarification_response()   — wraps a follow-up question in a QueryResponse.
  apply_affiliate_tags()           — rewrites product URLs with the affiliate tag.
"""

from app.core.config import get_settings
from app.models.responses import CategoryResult, ProductCard, QueryResponse


def build_recommendation_response(
    categories: list[CategoryResult],
    session_id: str | None = None,
    summary: str | None = None,
) -> QueryResponse:
    """
    Assemble a successful recommendations response.

    Args:
        categories: Ranked product results grouped by category.
        session_id: Active session ID, if any.
        summary: AI reasoning text shown to the user above the product list.

    Returns:
        QueryResponse with status='recommendations'.
    """
    return QueryResponse(
        status="recommendations",
        summary=summary,
        categories=categories,
        session_id=session_id,
    )


def build_clarification_response(
    message_or_follow_ups: str | list[str],
    session_id: str | None = None,
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
    )


def tag_affiliate_url(url: str) -> str:
    """
    Append the configured affiliate tag to a product URL.

    If AFFILIATE_TAG is empty or not configured, the original URL is
    returned unchanged.
    """
    settings = get_settings()
    if not settings.AFFILIATE_TAG:
        return url
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}tag={settings.AFFILIATE_TAG}"


def apply_affiliate_tags(products: list[ProductCard]) -> list[ProductCard]:
    """Return a new list of ProductCards with affiliate tags applied to all URLs."""
    return [p.model_copy(update={"url": tag_affiliate_url(p.url)}) for p in products]
