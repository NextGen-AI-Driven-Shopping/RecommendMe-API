"""
Ranking service — analyses all recommended products and picks the single
best match for the user based on their original query.

Flow:
1. Collect all products across every category.
2. Send them to the LLM with the user's original message as context.
3. LLM returns a ranked list + a clear "best pick" with a reason.
4. Return a RankingResult containing the best product and full ranked list.
"""

import json
from dataclasses import dataclass, field
from typing import List, Optional

from app.core.exceptions import AllProvidersFailedError, ProviderError, ProviderUnavailableError
from app.core.logger import get_logger
from app.models.internal import Category, Product

logger = get_logger(__name__)


# ── Output contract ──────────────────────────────────────────────────────────


@dataclass
class RankedProduct:
    """A product with its rank position and personalised explanation."""
    rank: int
    title: str
    category: str
    price: Optional[str] = None
    url: Optional[str] = None
    image_url: Optional[str] = None
    source: Optional[str] = None
    rating: Optional[float] = None
    why_its_good: str = ""        # general fit explanation
    why_best_for_you: str = ""    # specific to the user's query (only on rank 1)


@dataclass
class RankingResult:
    """Full output of the ranking step."""
    best_product: Optional[RankedProduct] = None
    ranked_list: List[RankedProduct] = field(default_factory=list)
    provider_used: Optional[str] = None


# ── Prompt ───────────────────────────────────────────────────────────────────


_RANKING_SYSTEM_PROMPT = """\
You are a personal shopping advisor. A user has described what they need, \
and you have a list of product options across several categories.

Your job:
1. Rank ALL products from best to worst match for THIS specific user.
2. Identify the single BEST product and write a short, personal explanation \
   of exactly why it is the top pick for this user's situation.

Return ONLY valid JSON — no markdown, no extra text.

JSON schema:
{
  "best_product": {
    "title": "<product title>",
    "category": "<category it belongs to>",
    "price": "<price string or null>",
    "url": "<url or null>",
    "image_url": "<image url or null>",
    "source": "<retailer or null>",
    "rating": <number or null>,
    "why_its_good": "<1 sentence — what makes this product generally good>",
    "why_best_for_you": "<2-3 sentences — why this is the perfect pick for THIS user based on their exact query>"
  },
  "ranked_list": [
    {
      "rank": 1,
      "title": "<product title>",
      "category": "<category>",
      "price": "<price or null>",
      "url": "<url or null>",
      "image_url": "<image url or null>",
      "source": "<retailer or null>",
      "rating": <number or null>,
      "why_its_good": "<1 sentence explanation>"
    }
  ]
}

Ranking rules:
- Prioritise products that match the user's stated budget, if mentioned.
- Prioritise products that match specific constraints (lightweight, beginner-friendly, etc.).
- Higher rating breaks ties.
- why_best_for_you must directly reference words or constraints from the user's query.
- Never invent prices, URLs, or ratings not present in the input data.
"""


def _build_ranking_messages(
    user_message: str,
    products_by_category: List[dict],
) -> List[dict]:
    import json as _json
    listings_text = _json.dumps(products_by_category, ensure_ascii=False, indent=2)
    user_content = (
        f"User's request: \"{user_message}\"\n\n"
        f"Product options:\n{listings_text}"
    )
    return [
        {"role": "system", "content": _RANKING_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


# ── Helpers ───────────────────────────────────────────────────────────────────


def _flatten_categories(categories: List[Category]) -> List[dict]:
    """
    Convert internal Category objects into a flat list of dicts
    that the LLM can reason about.
    """
    flat: List[dict] = []
    for cat in categories:
        for product in cat.products:
            flat.append({
                "category": cat.name,
                "title": product.title,
                "price": product.price,
                "url": product.url,
                "image_url": product.image_url,
                "source": product.source,
                "rating": product.rating,
                "explanation": product.explanation,
            })
    return flat


def _clean_json(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(
            line for line in lines if not line.startswith("```")
        ).strip()
    return text


def _parse_ranking_response(raw: str) -> tuple[Optional[RankedProduct], List[RankedProduct]]:
    """Parse the LLM's JSON into RankedProduct objects."""
    text = _clean_json(raw)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning(f"Ranking JSON parse failed: {exc} — raw: {text[:200]}")
        return None, []

    # Parse best product
    best: Optional[RankedProduct] = None
    bp = data.get("best_product")
    if bp and bp.get("title"):
        best = RankedProduct(
            rank=1,
            title=bp.get("title", ""),
            category=bp.get("category", ""),
            price=bp.get("price"),
            url=bp.get("url"),
            image_url=bp.get("image_url"),
            source=bp.get("source"),
            rating=float(bp["rating"]) if bp.get("rating") is not None else None,
            why_its_good=bp.get("why_its_good", ""),
            why_best_for_you=bp.get("why_best_for_you", ""),
        )

    # Parse full ranked list
    ranked: List[RankedProduct] = []
    for item in data.get("ranked_list", []):
        if not item.get("title"):
            continue
        try:
            ranked.append(
                RankedProduct(
                    rank=int(item.get("rank", len(ranked) + 1)),
                    title=item.get("title", ""),
                    category=item.get("category", ""),
                    price=item.get("price"),
                    url=item.get("url"),
                    image_url=item.get("image_url"),
                    source=item.get("source"),
                    rating=float(item["rating"]) if item.get("rating") is not None else None,
                    why_its_good=item.get("why_its_good", ""),
                )
            )
        except Exception as exc:
            logger.debug(f"Skipping malformed ranked item: {exc}")

    ranked.sort(key=lambda p: p.rank)
    return best, ranked


# ── Provider fallback ─────────────────────────────────────────────────────────


async def _call_provider(messages: list) -> tuple[str, str]:
    """Try providers in order: Gemini → GROQ → OpenAI → Ollama."""
    errors: list[str] = []
    providers_to_try = []

    try:
        from app.providers.gemini_provider import GeminiProvider
        providers_to_try.append(GeminiProvider())
    except ProviderUnavailableError:
        pass

    try:
        from app.providers.groq_provider import GroqProvider
        providers_to_try.append(GroqProvider())
    except ProviderUnavailableError:
        pass

    try:
        from app.providers.openai_provider import OpenAIProvider
        providers_to_try.append(OpenAIProvider())
    except ProviderUnavailableError:
        pass

    try:
        from app.providers.ollama_provider import OllamaProvider
        providers_to_try.append(OllamaProvider())
    except ProviderUnavailableError:
        pass

    if not providers_to_try:
        raise AllProvidersFailedError("No AI providers configured.")

    for provider in providers_to_try:
        try:
            raw = await provider.complete(messages, temperature=0.2, max_tokens=2048)
            return raw, provider.name
        except (ProviderError, ProviderUnavailableError) as exc:
            errors.append(f"{provider.name}: {exc}")
            logger.warning(f"Ranking: {provider.name} failed — trying next")

    raise AllProvidersFailedError(
        "All providers failed during ranking.", detail="; ".join(errors)
    )


# ── Public entry point ────────────────────────────────────────────────────────


async def rank_products(
    user_message: str,
    categories: List[Category],
) -> RankingResult:
    """
    Rank all products across all categories and identify the single best
    product for the user based on their original query.

    Args:
        user_message: The user's original shopping query.
        categories:   Enriched categories from recommender.py.

    Returns:
        RankingResult with best_product highlighted and full ranked_list.
    """
    flat_products = _flatten_categories(categories)

    if not flat_products:
        logger.warning("rank_products called with no products — skipping LLM call")
        return RankingResult()

    # Group by category for cleaner LLM context
    grouped: dict[str, list] = {}
    for p in flat_products:
        grouped.setdefault(p["category"], []).append(p)

    products_by_category = [
        {"category": cat, "products": prods}
        for cat, prods in grouped.items()
    ]

    messages = _build_ranking_messages(user_message, products_by_category)

    try:
        raw, provider_used = await _call_provider(messages)
        logger.info(f"Product ranking succeeded via {provider_used}")
    except AllProvidersFailedError as exc:
        logger.error(f"Ranking failed entirely: {exc}")
        return RankingResult()

    best, ranked_list = _parse_ranking_response(raw)

    if not best and ranked_list:
        # Graceful fallback: promote the top-ranked item as best
        best = ranked_list[0]
        best.why_best_for_you = best.why_its_good

    return RankingResult(
        best_product=best,
        ranked_list=ranked_list,
        provider_used=provider_used,
    )