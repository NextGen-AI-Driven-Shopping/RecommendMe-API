"""
Suggestions service — user-facing layer over the recommendation pipeline.

This is the single file you call from your API handler / controller.
It drives recommender.py → ranking.py under the hood and returns a
clean SuggestionResponse that is ready to serialise to JSON.

HOW THIS FILE IS ORGANISED
──────────────────────────
  1. Output dataclasses  (SuggestedProduct, SuggestionCategory, SuggestionResponse)
       → These define what the rest of the app sees. Do not change field names
         without coordinating with Sujay (Models) and Varun (API contract).

  2. Converter classes   (CategoryBuilder, RankedListBuilder)
       → Internal helpers that translate raw pipeline output (ReasoningResult)
         into the clean dataclasses above. Only used inside this file.

  3. SuggestionsService  (the main class)
       → Instantiate this and call .get_suggestions() from your route handler.
         This is the only class other files should import and use directly.

Usage:
    from app.services.suggestions import SuggestionsService

    service  = SuggestionsService()
    response = await service.get_suggestions(
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
from app.models.internal import ReasoningResult

logger = get_logger(__name__)


# ── 1. OUTPUT DATACLASSES ─────────────────────────────────────────────────────
#
# These are the objects that callers (route handlers, tests, etc.) receive.
# All fields are public and safe to serialise directly to JSON.
#
# NOTE: Fields marked Optional are intentionally nullable — a partially-enriched
# product from SerpAPI should never cause a crash here.
# ─────────────────────────────────────────────────────────────────────────────


@dataclass # The main product suggestion object returned to the caller.
class SuggestedProduct:
    """
    Represents a single product suggestion returned to the caller.

    Attributes
    ----------
    rank            : Position in the ranked list. 1 = best pick.
    title           : Product name as returned by SerpAPI.
    category        : The category this product belongs to (e.g. "Laptop").
    price           : Price string from SerpAPI (e.g. "₹45,000"). May be None.
    url             : Direct purchase link. May be None.
    image_url       : Thumbnail image URL from SerpAPI. May be None.
    source          : Platform name (e.g. "Amazon", "Flipkart"). May be None.
    rating          : Numeric rating out of 5. May be None if unavailable.
    why_its_good    : General explanation of why this product is a good choice.
    why_best_for_you: Personalised reason populated ONLY for rank == 1 (best pick).
                      Empty string for all other products.
    """

    rank: int
    title: str
    category: str
    price: Optional[str] = None
    url: Optional[str] = None
    image_url: Optional[str] = None
    source: Optional[str] = None
    rating: Optional[float] = None
    why_its_good: str = ""
    why_best_for_you: str = ""       # Only filled for the best pick (rank == 1)

    @property
    def is_best_pick(self) -> bool:
        """Returns True if this product is ranked #1 (the best pick)."""
        return self.rank == 1


@dataclass # Represents a category containing multiple SuggestedProduct objects.
class SuggestionCategory:
    """
    A named category containing all its SuggestedProduct objects.

    Used by tab-style or accordion UIs where products are grouped by category
    (e.g. "Laptops", "Bags", "Accessories") instead of shown as a flat list.

    Attributes
    ----------
    name     : Category name (e.g. "Laptop", "Backpack").
    products : All suggested products belonging to this category.
               Products here carry rank=0 (they are not globally ranked).
    """

    name: str
    products: List[SuggestedProduct] = field(default_factory=list)


@dataclass # The top-level response returned by SuggestionsService.get_suggestions().
class SuggestionResponse:
    """
    Top-level response returned by SuggestionsService.get_suggestions().

    This is what route handlers receive. All display logic should be driven
    from the fields and properties on this object.

    Attributes
    ----------
    raw_query       : Echo of the user's original message (useful for logging/UI).
    best_pick       : The single product most suited to the user's query.
                      None only if the pipeline produced zero products.
    alternatives    : All other products, ordered best → worst (rank 2 onwards).
    categories      : The same products grouped by category — for grouped UIs.
    provider_used   : Which LLM handled the category-reasoning step (e.g. "gpt-4o").

    Properties
    ----------
    has_results     : Quick boolean check — False if best_pick is None.
    all_ranked      : Best pick followed by alternatives as a single flat list.
    top_n(n)        : Slice the ranked list to the top N products.
    """

    raw_query: str
    best_pick: Optional[SuggestedProduct] = None
    alternatives: List[SuggestedProduct] = field(default_factory=list)
    categories: List[SuggestionCategory] = field(default_factory=list)
    provider_used: Optional[str] = None

    @property # Indicates whether the pipeline returned at least one product suggestion.
    def has_results(self) -> bool:
        """True if at least one product was returned by the pipeline."""
        return self.best_pick is not None

    @property# Returns the full ranked list: best pick at index 0, then alternatives.
    def all_ranked(self) -> List[SuggestedProduct]:
        """
        Returns the full ranked list: best pick at index 0, then alternatives.
        Safe to call even when best_pick is None.
        """
        if self.best_pick:
            return [self.best_pick] + self.alternatives
        return self.alternatives

    def top_n(self, n: int) -> List[SuggestedProduct]:
        """
        Return the top-N suggestions from the ranked list.
        Best pick is always at index 0 if it exists.

        Parameters
        ----------
        n : Number of products to return.
        """
        return self.all_ranked[:n]


# ── 2. CONVERTER CLASSES ──────────────────────────────────────────────────────
#
# These classes translate raw pipeline output (ReasoningResult from ranking.py)
# into the clean output dataclasses above. They are internal to this file —
# do not import them from outside suggestions.py.
#
# Why separate classes instead of one big function?
#   → CategoryBuilder and RankedListBuilder each own one transformation.
#     This makes them individually testable (Bhagyaraj's unit tests can call
#     each builder directly with a mock ReasoningResult).
# ─────────────────────────────────────────────────────────────────────────────


class CategoryBuilder: # Converts ReasoningResult → List[SuggestionCategory] for grouped UI views.
    """
    Converts a ReasoningResult into a list of SuggestionCategory objects.

    Used for grouped UIs (e.g. tab or accordion views) where products are
    displayed under their respective category headings.

    Products built here carry rank=0 because they are not globally ranked —
    they are simply grouped by category.

    Usage (internal to this file only):
        builder    = CategoryBuilder(reasoning)
        categories = builder.build()
    """

    def __init__(self, reasoning: ReasoningResult) -> None: 
        """
        Parameters
        ----------
        reasoning : The ReasoningResult returned by the recommendation pipeline.
                    Expected to carry .categories — a list of Category objects,
                    each with .name and .products.
        """
        self._reasoning = reasoning

    def build(self) -> List[SuggestionCategory]:
        """
        Iterate over each Category in the reasoning result, convert every
        Product inside it to a SuggestedProduct, and return the full list
        of SuggestionCategory objects.

        Products with no title are skipped — a title-less product cannot be
        displayed and is treated as malformed pipeline output.

        Returns
        -------
        List[SuggestionCategory]
            One SuggestionCategory per non-empty category in the reasoning result.
            Empty categories (all products had no title) are dropped.
        """
        result: List[SuggestionCategory] = []

        for cat in self._reasoning.categories:
            # Convert each Product in this category to a SuggestedProduct.
            # rank=0 signals these are unranked (category view only).
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
                if p.title          # skip products with no title
            ]

            # Only add this category if it has at least one valid product
            if suggestions:
                result.append(SuggestionCategory(name=cat.name, products=suggestions))

        return result


class RankedListBuilder: # Converts ReasoningResult → (best_pick, alternatives) tuple for ranked UI views.
    """
    Converts a ReasoningResult into a (best_pick, alternatives) tuple.

    The ranking step in ranking.py produces a flat list of RankedProduct objects.
    This class separates rank-1 (best pick) from the rest and maps them to
    SuggestedProduct objects for the caller.

    Usage (internal to this file only):
        builder              = RankedListBuilder(reasoning)
        best_pick, alts      = builder.build()
    """

    def __init__(self, reasoning: ReasoningResult) -> None:
        """
        Parameters
        ----------
        reasoning : The ReasoningResult returned by the recommendation pipeline.
                    Expected to carry:
                      .best_product    → the single top product (may be None)
                      .ranked_products → all ranked products including rank-1
        """
        self._reasoning = reasoning

    def build(self) -> tuple[Optional[SuggestedProduct], List[SuggestedProduct]]:
        """
        Extract the best pick and all alternatives from the reasoning result.

        The best pick comes from reasoning.best_product (rank 1, with
        personalised explanation). All other ranked products become alternatives.
        Rank-1 is skipped in ranked_products to avoid duplicating best_pick.

        Returns
        -------
        tuple[Optional[SuggestedProduct], List[SuggestedProduct]]
            (best_pick, alternatives)
            best_pick is None only if the pipeline produced no ranked products.
        """
        best_pick: Optional[SuggestedProduct] = None
        alternatives: List[SuggestedProduct] = []

        # ── Build the best pick (rank 1) ──────────────────────────────────────
        # best_product carries why_best_for_you — a personalised explanation
        # written by ranking.py specifically for the user's query context.
        bp = self._reasoning.best_product
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

        # ── Build alternatives (rank 2 and beyond) ────────────────────────────
        # ranked_products contains ALL ranked items including rank 1.
        # We skip rank 1 here because it is already captured as best_pick above.
        for rp in self._reasoning.ranked_products:
            if rp.rank == 1:
                continue        # already handled above as best_pick

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
                    # why_best_for_you is intentionally left empty for non-best picks
                )
            )

        return best_pick, alternatives


# ── 3. SUGGESTIONS SERVICE ────────────────────────────────────────────────────
#
# This is the only class that route handlers and other services should use.
# It orchestrates the full pipeline and delegates conversion work to the
# builder classes above.
#
# Why a class instead of a bare async function?
#   → Consistent with the team's class-based service pattern.
#   → Easy to mock in tests (Gagan/Bhagyaraj can patch SuggestionsService).
#   → A future version can accept injected dependencies (e.g. a custom logger
#     or a mock recommender) via __init__ without changing the call signature.
# ─────────────────────────────────────────────────────────────────────────────


class SuggestionsService: # The main service class to call from route handlers for product suggestions.
    """
    Orchestrates the full recommendation pipeline and returns a clean
    SuggestionResponse ready to be serialised and sent to the frontend.

    Pipeline flow triggered by get_suggestions():
        user_message
            └─► get_recommendations()   [recommender.py → ranking.py]
                    └─► ReasoningResult
                            ├─► RankedListBuilder  → best_pick + alternatives
                            └─► CategoryBuilder    → categories (grouped view)
                                    └─► SuggestionResponse  ← returned to caller

    The service catches all exceptions from the pipeline and returns an empty
    SuggestionResponse instead of propagating the error — the route handler
    can check response.has_results to decide how to respond to the user.

    Usage:
        service  = SuggestionsService()
        response = await service.get_suggestions(
            user_message="I need a laptop under ₹60,000",
            conversation_history=[],
        )
        if response.has_results:
            return response.best_pick
    """

    def __init__(self) -> None:
        # Logger is scoped to this class so log lines are easy to trace back
        # (they will appear as "app.services.suggestions" in structured logs).
        self._logger = get_logger(__name__)

    async def get_suggestions(
        self,
        user_message: str,
        conversation_history: Optional[List[dict]] = None,
    ) -> SuggestionResponse:
        """
        Run the full recommendation + ranking pipeline and return a
        SuggestionResponse ready for the route handler.

        Parameters
        ----------
        user_message
            The user's raw shopping query (e.g. "I need a tent for 3 days").
            Validation (length, injection checks) happens upstream in
            validators.py (Sai Kumar) before this method is called.

        conversation_history
            Prior conversation turns for multi-turn session support.
            Each entry must follow the format:
                {"role": "user" | "assistant", "content": "<text>"}
            Pass an empty list [] if this is the first turn.

        Returns
        -------
        SuggestionResponse
            .best_pick      → The #1 product with a personalised explanation.
                              None if the pipeline returned nothing.
            .alternatives   → All other products ranked #2 onwards.
            .categories     → All products grouped by category (for grouped UIs).
            .has_results    → False if best_pick is None (no results to show).
            .provider_used  → Which LLM handled the recommendation step.
        """
        history = conversation_history or []

        self._logger.info(f"get_suggestions called | query='{user_message[:80]}'")

        # ── Step 1: Run the recommendation pipeline ───────────────────────────
        # get_recommendations() in recommender.py handles:
        #   - intent extraction via GPT-4o
        #   - category generation
        #   - SerpAPI product fetch (with Redis cache if available)
        #   - GPT-4o ranking via ranking.py
        # On any failure we catch the exception and return an empty response
        # so the route handler is never left with an unhandled crash.
        try:
            from app.services.recommender import get_recommendations as _get_recommendations
        except (ImportError, AttributeError) as exc:
            self._logger.error("Recommendation pipeline function unavailable: %s", exc)
            return SuggestionResponse(raw_query=user_message)

        try:
            reasoning: ReasoningResult = await _get_recommendations(
                user_message=user_message,
                conversation_history=history,
            )
        except Exception as exc:
            self._logger.error(f"Recommendation pipeline failed: {exc}")
            # Return an empty response — caller should check .has_results
            return SuggestionResponse(raw_query=user_message)

        # ── Step 2: Convert pipeline output → output dataclasses ──────────────
        # RankedListBuilder extracts best_pick (rank 1) and all alternatives.
        best_pick, alternatives = RankedListBuilder(reasoning).build()

        # CategoryBuilder groups the same products by category for grouped UIs.
        categories = CategoryBuilder(reasoning).build()

        # ── Step 3: Assemble and return the final response ────────────────────
        response = SuggestionResponse(
            raw_query=user_message,
            best_pick=best_pick,
            alternatives=alternatives,
            categories=categories,
            provider_used=reasoning.provider_used,
        )

        # Log the outcome so it is traceable in production logs
        if response.has_results:
            self._logger.info(
                f"Suggestions ready | best='{best_pick.title}' "   # type: ignore[union-attr]
                f"| alternatives={len(alternatives)} | categories={len(categories)}"
            )
        else:
            self._logger.warning("get_suggestions returned no results")

        return response