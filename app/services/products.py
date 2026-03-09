"""
Product fetch service.

Queries the SerpAPI Google Shopping endpoint for products matching
the extracted categories and injects affiliate tracking tags into
all returned product URLs.
"""

from app.models.responses import ProductCard


async def fetch_products(category: str, query: str) -> list[ProductCard]:
    """
    Fetch raw (un-ranked) products from SerpAPI.

    Args:
        category: Product category string (e.g. "wireless headphones").
        query:    Original user query used to refine the search term.

    Returns:
        List of ProductCard objects populated from SerpAPI results.
    """
    # TODO: implement SerpAPI HTTP call and response parsing
    pass


def inject_affiliate_tag(url: str, tag: str) -> str:
    """
    Append an affiliate tracking tag to a product URL.

    Args:
        url: The original product page URL.
        tag: The affiliate tag value to append.

    Returns:
        URL with the tag query parameter appended.
    """
    if not tag:
        return url
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}tag={tag}"
