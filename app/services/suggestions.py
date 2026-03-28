"""
Suggestions service — user-facing layer over the recommendation pipeline.

This is the single file you call from your API handler / controller.
It drives recommender.py → ranking.py under the hood and returns a
clean SuggestionResponse that is ready to serialise to JSON.

Usage:
    from app.services.suggestions import get_suggestions, SuggestionResponse

    response = await get_suggestions(
        user_message="I need a lightweight laptop for college under $800",
        conversation_history=[],          # pass prior turns for multi-turn support
    )

    print(response.best_pick)             # the single top recommendation
    print(response.alternatives)          # the rest, ranked
    print(response.categories)            # grouped by category if you need them
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from app.core.logger import get_logger
from app.models.internal import Category, ReasoningResult
from app.services.recommender import get_recommendations

logger = get_logger(__name__)


# ── Public output contract ────────────────────────────────────────────────────


@dataclass
class SuggestedProduct:
    """
    A single product suggestion — safe to serialise directly to JSON.
    All fields are optional so a partially-enriched product never breaks.
    """

    rank: int
    title: str
    category: str
    price: Optional[str] = None
    url: Optional[str] = None
    image_url: Optional[str] = None
    source: Optional[str] = None
    rating: Optional[float] = None

    # Why this product is a good fit in general
    why_its_good: str = ""

    # Only populated on rank == 1 (the best pick)
    why_best_for_you: str = ""

    @property
    def is_best_pick(self) -> bool:
        return self.rank == 1


@dataclass
class SuggestionCategory:
    """A category with all its suggestions, for grouped-display UIs."""

    name: str
    products: List[SuggestedProduct] = field(default_factory=list)


@dataclass
class SuggestionResponse:
    """
    Top-level response returned by get_suggestions().

    Fields
    ------
    best_pick       The single product most suited to the user's query.
                    None only if the pipeline produced zero products.
    alternatives    All other products, ordered best → worst.
    categories      The same products grouped by category (useful for
                    tab/accordion UIs).
    provider_used   Which LLM handled the category-reasoning step.
    raw_query       Echo of the user's original message.
    """

    raw_query: str
    best_pick: Optional[SuggestedProduct] = None
    alternatives: List[SuggestedProduct] = field(default_factory=list)
    categories: List[SuggestionCategory] = field(default_factory=list)
    provider_used: Optional[str] = None

    # ── Convenience helpers ──────────────────────────────────────────────────

    @property
    def has_results(self) -> bool:
        return self.best_pick is not None

    @property
    def all_ranked(self) -> List[SuggestedProduct]:
        """Best pick followed by alternatives — full ranked list."""
        if self.best_pick:
            return [self.best_pick] + self.alternatives
        return self.alternatives

    def top_n(self, n: int) -> List[SuggestedProduct]:
        """Return the top-N suggestions (includes best_pick at index 0)."""
        return self.all_ranked[:n]


# ── Internal converters ───────────────────────────────────────────────────────


def _build_categories(reasoning: ReasoningResult) -> List[SuggestionCategory]:
    """
    Convert internal Category objects to SuggestionCategory objects.
    Products inside each category carry rank=0 (unranked view).
    """
    result: List[SuggestionCategory] = []
    for cat in reasoning.categories:
        suggestions = [
            SuggestedProduct(
                rank=0,
                title=p.title,
                category=cat.name,
                price=p.price,
                url=p.url,
                image_url=p.image_url,
                source=p.source,
                rating=p.rating,
                why_its_good=p.explanation or "",
            )
            for p in cat.products
            if p.title
        ]
        if suggestions:
            result.append(SuggestionCategory(name=cat.name, products=suggestions))
    return result


def _build_ranked_list(reasoning: ReasoningResult) -> tuple[
    Optional[SuggestedProduct], List[SuggestedProduct]
]:
    """
    Convert RankedProduct objects from ranking.py into SuggestedProduct.
    Returns (best_pick, alternatives).
    """
    best_pick: Optional[SuggestedProduct] = None
    alternatives: List[SuggestedProduct] = []

    # Best product (rank 1 with personalised reason)
    bp = reasoning.best_product
    if bp:
        best_pick = SuggestedProduct(
            rank=1,
            title=bp.title,
            category=bp.category,
            price=bp.price,
            url=bp.url,
            image_url=bp.image_url,
            source=bp.source,
            rating=bp.rating,
            why_its_good=getattr(bp, "why_its_good", ""),
            why_best_for_you=getattr(bp, "why_best_for_you", ""),
        )

    # Rest of the ranked list (skip rank 1 — already in best_pick)
    for rp in reasoning.ranked_products:
        if rp.rank == 1:
            continue
        alternatives.append(
            SuggestedProduct(
                rank=rp.rank,
                title=rp.title,
                category=rp.category,
                price=rp.price,
                url=rp.url,
                image_url=rp.image_url,
                source=rp.source,
                rating=rp.rating,
                why_its_good=getattr(rp, "why_its_good", ""),
            )
        )

    return best_pick, alternatives


# ── Public entry point ────────────────────────────────────────────────────────


async def get_suggestions(
    user_message: str,
    conversation_history: Optional[List[dict]] = None,
) -> SuggestionResponse:
    """
    Run the full recommendation + ranking pipeline and return a
    user-facing SuggestionResponse.

    Parameters
    ----------
    user_message            The user's raw shopping query.
    conversation_history    Prior conversation turns for multi-turn support.
                            Each turn: {"role": "user"|"assistant", "content": "..."}

    Returns
    -------
    SuggestionResponse
        .best_pick          → the #1 product with why_best_for_you explanation
        .alternatives       → remaining products ranked #2 onwards
        .categories         → all products grouped by category
        .has_results        → False if the pipeline produced nothing
    """
    history = conversation_history or []

    logger.info(f"get_suggestions called | query='{user_message[:80]}'")

    # Run the full pipeline (intent → categories → SerpAPI → ranking)
    try:
        reasoning: ReasoningResult = await get_recommendations(
            user_message=user_message,
            conversation_history=history,
        )
    except Exception as exc:
        logger.error(f"Recommendation pipeline failed: {exc}")
        # Return an empty response rather than crashing the caller
        return SuggestionResponse(raw_query=user_message)

    # Convert ranked products → SuggestedProduct objects
    best_pick, alternatives = _build_ranked_list(reasoning)

    # Convert categories → SuggestionCategory objects (for grouped UIs)
    categories = _build_categories(reasoning)

    response = SuggestionResponse(
        raw_query=user_message,
        best_pick=best_pick,
        alternatives=alternatives,
        categories=categories,
        provider_used=reasoning.provider_used,
    )

    if response.has_results:
        logger.info(
            f"Suggestions ready | best='{best_pick.title}' "  # type: ignore[union-attr]
            f"| alternatives={len(alternatives)} | categories={len(categories)}"
        )
    else:
        logger.warning("get_suggestions returned no results")

    return response