"""
SERP product retrieval service (Step 6 of Flow.md).

Fetches real product listings from SerpAPI for each Product Type.
Each Product Type name drives one SERP search query.

Rules per Flow.md:
- Up to 10 product items per Product Type
- Minimum 5 valid items for card rendering (otherwise description-only)
- Retry once on SERP failure per Product Type
- Normalize all prices to INR
- Never generate fake product names
"""

from __future__ import annotations

import re
from typing import Optional

import httpx

from app.config.settings import get_settings
from app.core.logger import get_logger
from app.models.internal import ProductItem

logger = get_logger(__name__)

MAX_ITEMS_PER_TYPE = 10
MIN_ITEMS_FOR_CARDS = 5
SERP_TIMEOUT = 8.0


def _normalize_price_to_inr(raw_price: str | None) -> str:
    """
    Normalize price to INR format.

    If the price doesn't have INR/₹ indicator, assume it's already in the
    local SERP currency and return as-is with ₹ prefix.
    """
    if not raw_price:
        return ""

    cleaned = str(raw_price).strip()
    if not cleaned:
        return ""

    # Already in INR
    if "₹" in cleaned or "INR" in cleaned.upper():
        return cleaned

    # Extract numeric value
    numeric = re.sub(r"[^\d.,]", "", cleaned)
    if not numeric:
        return cleaned

    # Try to parse the value
    try:
        # Handle comma-separated numbers (Indian format: 1,45,000)
        value = float(numeric.replace(",", ""))
        if value > 0:
            return f"₹{value:,.0f}"
    except (ValueError, TypeError):
        pass

    return cleaned


async def fetch_product_items(
    product_type_name: str,
    *,
    context_signals: dict | None = None,
) -> list[ProductItem]:
    """
    Fetch product items from SerpAPI for a single Product Type.

    Args:
        product_type_name: The functional class name (drives the SERP query).
        context_signals: Optional signals like region, price range for query tuning.

    Returns:
        List of ProductItem objects (up to MAX_ITEMS_PER_TYPE).
        Empty list if SERP fails completely.
    """
    settings = get_settings()
    api_key = settings.SERPAPI_KEY

    if not api_key:
        logger.warning("SERPAPI_KEY not configured; skipping SERP fetch for %s", product_type_name)
        return []

    # Build search query from product type name + optional context
    search_query = product_type_name
    if context_signals:
        if context_signals.get("price_range"):
            search_query += f" {context_signals['price_range']}"
        if context_signals.get("region"):
            search_query += f" in {context_signals['region']}"

    items = await _serp_search(api_key, search_query)

    if not items:
        # Retry once on failure per Flow.md
        logger.info("SERP retry for product_type=%s", product_type_name)
        items = await _serp_search(api_key, product_type_name)

    return items[:MAX_ITEMS_PER_TYPE]


async def _serp_search(api_key: str, query: str) -> list[ProductItem]:
    """Execute a SerpAPI Google Shopping search and normalize results."""
    params = {
        "engine": "google_shopping",
        "q": query,
        "api_key": api_key,
        "hl": "en",
        "gl": "in",  # India for INR pricing
        "num": str(MAX_ITEMS_PER_TYPE),
    }

    try:
        async with httpx.AsyncClient(timeout=SERP_TIMEOUT) as client:
            response = await client.get(
                "https://serpapi.com/search",
                params=params,
            )
            response.raise_for_status()
            data = response.json()
    except httpx.TimeoutException:
        logger.warning("SERP timeout for query=%s", query[:80])
        return []
    except httpx.HTTPStatusError as exc:
        logger.warning("SERP HTTP error %d for query=%s", exc.response.status_code, query[:80])
        return []
    except Exception as exc:
        logger.warning("SERP request failed for query=%s: %s", query[:80], str(exc)[:120])
        return []

    shopping_results = data.get("shopping_results", [])
    if not shopping_results:
        # Try inline shopping results as fallback
        shopping_results = data.get("inline_shopping_results", [])

    items: list[ProductItem] = []
    for result in shopping_results:
        if len(items) >= MAX_ITEMS_PER_TYPE:
            break

        title = str(result.get("title", "")).strip()
        if not title:
            continue

        # Extract and normalize fields
        raw_price = result.get("extracted_price") or result.get("price")
        price_str = _normalize_price_to_inr(str(raw_price) if raw_price else None)

        image_url = str(result.get("thumbnail", "") or result.get("thumbnail_url", "")).strip()
        buy_link = str(result.get("link", "") or result.get("product_link", "")).strip()
        source = str(result.get("source", "") or result.get("seller", "")).strip()

        # Rating
        rating = None
        raw_rating = result.get("rating")
        if raw_rating is not None:
            try:
                rating = float(raw_rating)
            except (ValueError, TypeError):
                pass

        # Reviews count
        reviews_count = None
        raw_reviews = result.get("reviews")
        if raw_reviews is not None:
            try:
                reviews_count = int(str(raw_reviews).replace(",", ""))
            except (ValueError, TypeError):
                pass

        # Delivery info
        delivery_info = None
        raw_delivery = result.get("delivery")
        if isinstance(raw_delivery, str) and raw_delivery.strip():
            delivery_info = raw_delivery.strip()

        # Short description from SERP snippet
        short_description = str(result.get("snippet", "") or result.get("description", "")).strip()

        # Brand extraction
        brand = None
        raw_brand = result.get("brand")
        if isinstance(raw_brand, str) and raw_brand.strip():
            brand = raw_brand.strip()

        item = ProductItem(
            product_name=title,
            image_url=image_url,
            price_inr=price_str,
            short_description=short_description,
            buy_link=buy_link,
            rating=rating,
            brand=brand,
            reviews_count=reviews_count,
            delivery_info=delivery_info,
            source=source or None,
        )

        items.append(item)

    logger.info(
        "SERP returned %d items for query=%s (valid=%d)",
        len(items),
        query[:60],
        sum(1 for i in items if i.has_required_fields),
    )

    return items


# Legacy function name for backward compatibility during migration
async def fetch_products(category: str = "", query: str = "") -> list:
    """
    Legacy wrapper — routes to new fetch_product_items.

    Returns list of ProductCard-compatible dicts for backward compat.
    """
    search_query = f"{category} {query}".strip() if category else query.strip()
    if not search_query:
        return []

    items = await fetch_product_items(search_query)

    # Convert to legacy format
    from app.models.responses import ProductItemResponse
    return [
        ProductItemResponse(
            product_name=item.product_name,
            image_url=item.image_url,
            price_inr=item.price_inr,
            short_description=item.short_description,
            buy_link=item.buy_link,
            rating=item.rating,
            brand=item.brand,
            reviews_count=item.reviews_count,
            delivery_info=item.delivery_info,
            availability=item.availability,
            source=item.source,
        )
        for item in items
    ]
