"""Product fetch service backed by SerpAPI Google Shopping.

Changes from original
─────────────────────
* HTTP 429 from SerpAPI immediately sets system_state["serpapi_available"]=False
  via mark_serpapi_quota_exhausted(). All subsequent calls in this process
  skip SerpAPI entirely — no blind retry on an exhausted quota.

* Google fallback now uses follow_redirects=True and sends Accept-Language so
  Google does not redirect/block the request.

* Request-scoped deduplication cache (_FETCH_CACHE) keyed on
  "{category}:{query}". The same pair is never fetched twice within one
  process request cycle.  Cache is intentionally NOT cleared between requests
  because products don't change in seconds — this also acts as a short-term
  in-process cache.

* Retry loop is capped at MAX_RETRIES (1) so a transient failure triggers at
  most one retry before giving up.

* Returns None — never a fake card — when all data sources fail.  The caller
  (query.py) is responsible for deciding what to show the user.
"""

from __future__ import annotations

import re
from time import sleep
from urllib.parse import unquote, urlparse

import httpx

from app.config.settings import get_settings
from app.core.logger import get_logger
from app.models.responses import ProductCard
from app.services.system_state import (
    MAX_RETRIES,
    is_serpapi_available,
    mark_serpapi_quota_exhausted,
)

logger = get_logger(__name__)

# ── Request-scoped deduplication cache ───────────────────────────────────────
# Key: "{category}:{query}"  Value: list[ProductCard] | None
# Populated on first fetch; subsequent calls with same key return immediately.
_FETCH_CACHE: dict[str, list[ProductCard] | None] = {}


def _cache_key(category: str, query: str) -> str:
    return f"{category.strip().lower()}:{query.strip().lower()}"


# ── Public API ────────────────────────────────────────────────────────────────


async def fetch_products(category: str, query: str) -> list[ProductCard] | None:
    """
    Fetch raw (un-ranked) products from SerpAPI Google Shopping.

    Pipeline
    --------
    1. Return cached result if this (category, query) was already fetched.
    2. If SerpAPI quota is exhausted, skip straight to Google fallback.
    3. Try SerpAPI (up to MAX_RETRIES+1 attempts).
       - 429 → disable SerpAPI globally, fall through.
       - 401/403 → fall through to Google fallback.
    4. Try Google fallback with proper headers and redirect following.
    5. Return None if everything fails — never a fake card.

    Args:
        category: Product category string (e.g. "wireless headphones").
        query:    Original user query used to refine the search term.

    Returns:
        List of ProductCard objects, or None if all sources failed.
    """
    key = _cache_key(category, query)

    # ── 1. Cache hit ──────────────────────────────────────────────────────────
    if key in _FETCH_CACHE:
        logger.debug("fetch_products cache hit category=%s query=%s", category, query)
        return _FETCH_CACHE[key]

    # ── 2. SerpAPI disabled → go straight to fallback ─────────────────────────
    if not is_serpapi_available():
        logger.warning(
            "SerpAPI quota exhausted — skipping to Google fallback category=%s", category
        )
        result = await _fetch_products_from_google(category=category, query=query)
        _FETCH_CACHE[key] = result
        return result

    settings = get_settings()

    if not settings.SERPAPI_KEY:
        logger.warning(
            "SERPAPI_KEY not set — falling back to direct Google fetch query=%s", query
        )
        result = await _fetch_products_from_google(category=category, query=query)
        _FETCH_CACHE[key] = result
        return result

    # ── 3. SerpAPI (with capped retry) ────────────────────────────────────────
    params = {
        "engine": "google_shopping",
        "q": f"{category} {query}".strip(),
        "api_key": settings.SERPAPI_KEY,
        "num": 10,
        "gl": "in",
        "hl": "en",
        "google_domain": "google.co.in",
    }

    result = await _try_serpapi(params, category=category, query=query)
    _FETCH_CACHE[key] = result
    return result


async def _try_serpapi(
    params: dict, *, category: str, query: str
) -> list[ProductCard] | None:
    """Try SerpAPI with MAX_RETRIES, handling 429 quota errors specially."""
    for attempt in range(MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get("https://serpapi.com/search", params=params)

            # ── Quota exhausted ───────────────────────────────────────────────
            if response.status_code == 429:
                logger.error(
                    "SerpAPI quota exhausted (HTTP 429) — disabling SerpAPI globally. "
                    "category=%s attempt=%d",
                    category,
                    attempt + 1,
                )
                mark_serpapi_quota_exhausted()
                return await _fetch_products_from_google(category=category, query=query)

            # ── Auth failure ──────────────────────────────────────────────────
            if response.status_code in (401, 403):
                logger.error(
                    "SerpAPI authentication failed category=%s — verify SERPAPI_KEY. "
                    "Response: %s",
                    category,
                    response.text[:300],
                )
                return await _fetch_products_from_google(category=category, query=query)

            response.raise_for_status()

        except httpx.HTTPStatusError as exc:
            body = ""
            try:
                body = exc.response.text[:300]
            except Exception:
                pass
            logger.error(
                "SerpAPI HTTP error category=%s status=%s body=%s attempt=%d/%d",
                category,
                exc.response.status_code,
                body,
                attempt + 1,
                MAX_RETRIES + 1,
            )
            if attempt < MAX_RETRIES:
                sleep(2**attempt)
                continue
            return await _fetch_products_from_google(category=category, query=query)

        except httpx.HTTPError as exc:
            logger.error(
                "SerpAPI request failed category=%s error=%s attempt=%d/%d",
                category,
                str(exc)[:200],
                attempt + 1,
                MAX_RETRIES + 1,
            )
            if attempt < MAX_RETRIES:
                sleep(2**attempt)
                continue
            return await _fetch_products_from_google(category=category, query=query)

        # ── Parse response ────────────────────────────────────────────────────
        data = response.json()
        items = data.get("shopping_results", [])
        if not isinstance(items, list):
            logger.warning(
                "SerpAPI returned invalid shopping_results format: %s", str(data)[:200]
            )
            return await _fetch_products_from_google(category=category, query=query)

        settings = get_settings()
        products: list[ProductCard] = []
        for item in items:
            title = str(item.get("title") or "").strip()
            link = str(item.get("product_link") or item.get("link") or "").strip()
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
            logger.info(
                "SerpAPI success category=%s products=%d", category, len(products)
            )
            return products

        logger.warning(
            "SerpAPI returned no product cards — falling back to Google fetch category=%s",
            category,
        )
        return await _fetch_products_from_google(category=category, query=query)

    # Should never reach here
    return await _fetch_products_from_google(category=category, query=query)


# ── Google Fallback ───────────────────────────────────────────────────────────


async def _fetch_products_from_google(
    category: str, query: str
) -> list[ProductCard] | None:
    """
    Direct Google Shopping fallback used when SerpAPI fails or is unavailable.

    Sends proper browser headers and follows redirects so Google's bot
    protection and HTTP 302 responses are handled correctly.
    """
    search_query = f"{category} {query}".strip()
    params = {
        "q": search_query,
        "tbm": "shop",
        "hl": "en",
    }
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        async with httpx.AsyncClient(
            timeout=20.0,
            headers=headers,
            follow_redirects=True,   # CRITICAL: handles HTTP 302 from Google
        ) as client:
            response = await client.get("https://www.google.com/search", params=params)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error(
            "Direct Google fallback failed category=%s error=%s",
            category,
            str(exc)[:200],
        )
        return None

    html = response.text
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

    if products:
        logger.info(
            "Google fallback success category=%s products=%d", category, len(products)
        )
        return products

    logger.warning(
        "Google fallback returned no products category=%s", category
    )
    return None


# ── Helpers ───────────────────────────────────────────────────────────────────


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
