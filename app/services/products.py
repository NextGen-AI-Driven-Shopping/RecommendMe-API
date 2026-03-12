"""
Product fetch service.

Queries the SerpAPI Google Shopping endpoint for products matching
the extracted search categories and injects optional affiliate tracking
tags into all returned product URLs.

TODO: Full SerpAPI HTTP integration pending from products service owner.
      The function signatures and return types are finalised.
"""

from app.core.config import get_settings
from app.core.logger import get_logger
from app.models.responses import ProductCard

logger = get_logger(__name__)


async def fetch_products(category: str, query: str) -> list[ProductCard] | None:
    """
    Fetch raw (un-ranked) products from SerpAPI Google Shopping.

    Args:
        category: Product category string derived from intent extraction
                  (e.g. "wireless noise-cancelling headphones").
        query:    Original user query used to refine the search term.

    Returns:
        List of ProductCard objects populated from SerpAPI results, or
        None if the SerpAPI key is not configured / service not yet implemented.

    TODO: Implementation pending from products service owner.
          Replace the placeholder body below with the real SerpAPI HTTP call.

    Example skeleton:
        import httpx
        settings = get_settings()
        if not settings.SERPAPI_KEY:
            return None
        params = {
            "engine": "google_shopping",
            "q": f"{category} {query}".strip(),
            "api_key": settings.SERPAPI_KEY,
            "num": 10,
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get("https://serpapi.com/search", params=params)
            resp.raise_for_status()
            items = resp.json().get("shopping_results", [])
        return [
            ProductCard(
                title=item.get("title", ""),
                price=item.get("price"),
                url=inject_affiliate_tag(item.get("link", "#"), settings.AFFILIATE_TAG),
                image_url=item.get("thumbnail"),
                source=item.get("source"),
                rating=item.get("rating"),
            )
            for item in items
        ]
    """
    settings = get_settings()

    if not settings.SERPAPI_KEY:
        # Temporary placeholder until the SerpAPI key is configured in .env
        logger.warning("SERPAPI_KEY not set; fetch_products returning None.")
        return None

    # TODO: Implementation pending from module owner.
    # Temporary placeholder until feature implementation is completed.
    return None


def inject_affiliate_tag(url: str, tag: str) -> str:
    """
    Append an affiliate tracking tag to a product URL.

    Args:
        url: The original product page URL.
        tag: The affiliate tag value to append (pass empty string to skip).

    Returns:
        URL with the tag query parameter appended, or the original URL if
        tag is empty.
    """
    if not tag:
        return url
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}tag={tag}"
