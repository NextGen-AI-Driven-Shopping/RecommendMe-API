"""
Response formatting utilities.

Assembles final QueryResponse objects from ranked product data and
handles affiliate URL tag injection for all outbound product links.
"""

from app.core.config import get_settings
from app.models.responses import CategoryResult, ProductCard, QueryResponse


def build_recommendation_response(
    categories: list[CategoryResult],
    session_id: str | None = None,
) -> QueryResponse:
    """
    Assemble a successful recommendations response.

    Args:
        categories: Ranked product results grouped by category.
        session_id: Active session ID, if any.

    Returns:
        QueryResponse with status='recommendations'.
    """
    return QueryResponse(
        status="recommendations",
        categories=categories,
        session_id=session_id,
    )


def build_clarification_response(
    follow_up: str,
    session_id: str | None = None,
) -> QueryResponse:
    """
    Assemble a clarification-needed response.

    Args:
        follow_up: The clarifying question to present to the user.
        session_id: Active session ID, if any.

    Returns:
        QueryResponse with status='clarification_needed'.
    """
    return QueryResponse(
        status="clarification_needed",
        message=follow_up,
        session_id=session_id,
    )


def tag_affiliate_url(url: str) -> str:
    """
    Append the configured affiliate tag to a product URL.

    If no affiliate tag is configured, the original URL is returned unchanged.
    """
    settings = get_settings()
    if not settings.affiliate_tag:
        return url
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}tag={settings.affiliate_tag}"


def apply_affiliate_tags(products: list[ProductCard]) -> list[ProductCard]:
    """Return a new list of ProductCards with affiliate tags applied to all URLs."""
    return [p.model_copy(update={"url": tag_affiliate_url(p.url)}) for p in products]
