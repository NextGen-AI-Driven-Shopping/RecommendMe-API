"""Product fetch service backed by SerpAPI Google Shopping."""

from __future__ import annotations

import re
from urllib.parse import unquote, urlparse

import httpx

from app.config.settings import get_settings
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
        None if the SerpAPI key is not configured or the provider fails.
    """
    settings = get_settings()

    if not settings.SERPAPI_KEY:
        logger.warning("SERPAPI_KEY not set; falling back to direct Google fetch for query=%s", query)
        return await _fetch_products_from_google(category=category, query=query)

    params = {
        "engine": "google_shopping",
        "q": f"{category} {query}".strip(),
        "api_key": settings.SERPAPI_KEY,
        "num": 10,
        "gl": "in",
        "hl": "en",
        "google_domain": "google.co.in",
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get("https://serpapi.com/search", params=params)

        if response.status_code in (401, 403):
            logger.error(
                "SerpAPI authentication failed category=%s — verify SERPAPI_KEY. Response: %s",
                category,
                response.text[:300],
            )
            return await _fetch_products_from_google(category=category, query=query)

        response.raise_for_status()
    except httpx.HTTPError as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", "unknown")
        body = ""
        if hasattr(exc, "response") and exc.response is not None:
            try:
                body = exc.response.text[:300]
            except Exception:
                pass
        logger.error("SerpAPI request failed category=%s status=%s body=%s", category, status_code, body)
        return await _fetch_products_from_google(category=category, query=query)

    data = response.json()
    items = data.get("shopping_results", [])
    if not isinstance(items, list):
        logger.warning("SerpAPI returned invalid shopping_results format: %s", str(data)[:200])
        return await _fetch_products_from_google(category=category, query=query)

    products: list[ProductCard] = []
    for item in items:
        title = str(item.get("title") or "").strip()
        # Prefer direct product URL; fall back to Google Shopping listing link.
        link = (
            str(item.get("product_link") or item.get("link") or "").strip()
        )
        if not title or not link:
            continue

        rating_raw = item.get("rating")
        rating_value = float(rating_raw) if isinstance(rating_raw, (int, float)) else None

        reviews_raw = item.get("reviews")
        reviews_value = int(reviews_raw) if isinstance(reviews_raw, (int, float)) else None

        price_raw = item.get("price")
        price_str = str(price_raw).strip() if price_raw is not None else None

        products.append(
            ProductCard(
                title=title,
                price=price_str or None,
                url=inject_affiliate_tag(link, settings.AFFILIATE_TAG),
                image_url=item.get("thumbnail") or None,
                source=item.get("source") or None,
                rating=rating_value,
                reviews=reviews_value,
                explanation=None,
            )
        )

    if products:
        return products

    logger.warning("SerpAPI returned no product cards; falling back to direct Google fetch.")
    return await _fetch_products_from_google(category=category, query=query)


async def _fetch_products_from_google(category: str, query: str) -> list[ProductCard] | None:
    """Direct Google fallback used only when SerpAPI fails or returns nothing."""
    search_query = f"{category} {query}".strip()
    params = {
        "q": search_query,
        "tbm": "shop",
        "hl": "en",
    }

    try:
        async with httpx.AsyncClient(
            timeout=20.0,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            },
        ) as client:
            response = await client.get("https://www.google.com/search", params=params)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error("Direct Google fallback failed category=%s error=%s", category, str(exc)[:200])
        return None

    html = response.text
    # Parse encoded redirect links produced by Google search result anchors.
    matches = re.findall(r'href="/url\?q=([^"&]+)[^"]*"', html)

    products: list[ProductCard] = []
    seen_urls: set[str] = set()
    for encoded in matches:
        if len(products) >= 10:
            break
        candidate_url = unquote(encoded)
        if not candidate_url.startswith("http"):
            continue
        if "google.com" in urlparse(candidate_url).netloc:
            continue
        if candidate_url in seen_urls:
            continue
        seen_urls.add(candidate_url)

        domain = urlparse(candidate_url).netloc.replace("www.", "")
        title = _title_from_url(candidate_url)

        products.append(
            ProductCard(
                title=title,
                price=None,
                url=candidate_url,
                image_url=None,
                source=domain or "Google",
                rating=None,
                reviews=None,
                explanation="Fetched from direct Google fallback because SerpAPI was unavailable.",
            )
        )

    return products or None


def _title_from_url(url: str) -> str:
    parsed = urlparse(url)
    slug = parsed.path.strip("/").split("/")[-1]
    if not slug:
        return parsed.netloc.replace("www.", "") or "Product result"

    slug = slug.replace("-", " ").replace("_", " ")
    slug = re.sub(r"\s+", " ", slug).strip()
    if not slug:
        return parsed.netloc.replace("www.", "") or "Product result"
    return slug[:80].title()


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
