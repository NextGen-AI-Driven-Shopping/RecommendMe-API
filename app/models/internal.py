"""
app/models/internal.py

Internal Pydantic models used ONLY within the backend pipeline.
These are NEVER serialised into API responses — they are intermediate
data structures that services pass between each other.

WHO USES THESE MODELS
─────────────────────
  recommender.py  (Lahari)  → produces ReasoningResult
  ranking.py      (Sharanu) → produces RankedProduct, populates ReasoningResult
  suggestions.py  (your contribution) → consumes ReasoningResult

DO NOT expose these in API responses.
For API-facing schemas, see requests.py and responses.py.

STRUCTURE OVERVIEW
──────────────────
  Product           Raw product data fetched from SerpAPI (one listing).
  RankedProduct     A Product that has been ranked and explained by GPT-4o.
  Category          A named group of Products (e.g. "Laptop", "Backpack").
  ReasoningResult   The complete output of the recommendation pipeline —
                    this is what recommender.py returns and suggestions.py reads.
"""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


# ── 1. PRODUCT ────────────────────────────────────────────────────────────────
#
# Represents a single raw product listing as returned by SerpAPI.
# Populated by products.py (Vrandha) during the SerpAPI fetch step.
# Used inside Category to hold the products belonging to that category.
# ─────────────────────────────────────────────────────────────────────────────

class Product(BaseModel): # Represents a single raw product listing from SerpAPI, with optional fields.
    """
    A single raw product fetched from SerpAPI Google Shopping results.

    All fields except `title` are Optional because SerpAPI does not
    guarantee every field is present for every listing.

    Attributes
    ----------
    title       : Product name as returned by SerpAPI. Required.
    price       : Price string (e.g. "₹45,000" or "$799"). May be absent.
    url         : Direct purchase link. May be absent.
    image_url   : Thumbnail URL from SerpAPI. May be absent.
    source      : Platform name (e.g. "Amazon", "Flipkart"). May be absent.
    rating      : Numeric rating out of 5. May be absent.
    explanation : Why this product fits the user's query — written by ranking.py
                  (Sharanu) via GPT-4o. Empty string if ranking hasn't run yet.
    """

    title: str
    price: Optional[str] = None
    url: Optional[str] = None
    image_url: Optional[str] = None
    source: Optional[str] = None
    rating: Optional[float] = None
    explanation: str = ""           # Populated by ranking.py after GPT-4o ranking


# ── 2. RANKED PRODUCT ────────────────────────────────────────────────────────
#
# A Product that has been ranked by ranking.py (Sharanu) via GPT-4o.
# Extends Product with ranking position and personalised explanations.
#
# The rank-1 product (best pick) additionally gets a `why_best_for_you`
# explanation tailored to the user's specific query and session context.
# ─────────────────────────────────────────────────────────────────────────────

class RankedProduct(BaseModel): # A Product that has been ranked and explained by GPT-4o, with rank and personalised explanations.
    """
    A product that has been ranked and explained by the GPT-4o ranking step.

    Produced by ranking.py (Sharanu) and stored in ReasoningResult.
    Consumed by suggestions.py to build SuggestedProduct objects.

    Attributes
    ----------
    rank              : Global rank across all categories. 1 = best pick.
    title             : Product name.
    category          : Category this product belongs to (e.g. "Laptop").
    price             : Price string. May be absent.
    url               : Purchase link. May be absent.
    image_url         : Thumbnail URL. May be absent.
    source            : Platform name. May be absent.
    rating            : Numeric rating out of 5. May be absent.
    why_its_good      : General explanation of why this product is a strong choice.
                        Written by GPT-4o in ranking.py. Present for all ranks.
    why_best_for_you  : Personalised explanation specific to the user's query.
                        ONLY populated for rank == 1 (the best pick).
                        Empty string for all other ranks.
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
    why_best_for_you: str = ""      # Only populated for rank == 1


# ── 3. CATEGORY ───────────────────────────────────────────────────────────────
#
# A named product category with its associated raw Product listings.
# Produced by recommender.py (Lahari) after GPT-4o intent extraction.
# Each category corresponds to one SerpAPI query (e.g. "lightweight laptop
# under ₹60,000") whose results are stored as Product objects inside it.
# ─────────────────────────────────────────────────────────────────────────────

class Category(BaseModel): # A product category identified from the user's query, with its raw Product listings.
    """
    A product category identified from the user's query, with its products.

    Produced by recommender.py (Lahari) during the intent extraction step.
    Each Category maps to one SerpAPI search query.
    Consumed by suggestions.py (CategoryBuilder) to build grouped UI views.

    Attributes
    ----------
    name        : Category label as identified by GPT-4o (e.g. "Laptop", "Bag").
    products    : Raw Product listings fetched from SerpAPI for this category.
                  Populated by products.py (Vrandha). May be empty if SerpAPI
                  returned no results for this category.
    """

    name: str
    products: List[Product] = Field(default_factory=list)


# ── 4. REASONING RESULT ───────────────────────────────────────────────────────
#
# The complete output of the recommendation pipeline.
# This is what recommender.py (Lahari) returns and what suggestions.py reads.
#
# Flow that produces this object:
#   1. GPT-4o extracts intent and identifies Categories          [recommender.py]
#   2. SerpAPI fetches Product listings per Category             [products.py]
#   3. GPT-4o ranks products and writes explanations             [ranking.py]
#   4. ReasoningResult is assembled with all of the above        [recommender.py]
#   5. suggestions.py reads this and converts it to SuggestionResponse
# ─────────────────────────────────────────────────────────────────────────────

class ReasoningResult(BaseModel):# The complete output of the recommendation + ranking pipeline, containing ranked products, categories, and metadata.
    """
    The complete output of the recommendation + ranking pipeline.

    Produced by recommender.py (Lahari) and consumed by suggestions.py.
    Contains everything needed to build the final SuggestionResponse.

    Attributes
    ----------
    best_product        : The single highest-ranked product (rank == 1) with a
                          personalised explanation. None if the pipeline produced
                          no results (e.g. SerpAPI returned nothing).

    ranked_products     : All products across all categories, sorted by rank.
                          Includes the rank-1 product — suggestions.py skips it
                          when building alternatives to avoid duplication.

    categories          : All categories with their raw Product listings, used
                          for grouped (tab/accordion) UI views.

    provider_used       : Which LLM handled the recommendation step.
                          Typically "gpt-4o" but may differ if a fallback ran
                          (e.g. "gpt-4o-mini" if the primary model was unavailable).
                          None if the pipeline failed before the LLM step.
    """

    best_product: Optional[RankedProduct] = None
    ranked_products: List[RankedProduct] = Field(default_factory=list)
    categories: List[Category] = Field(default_factory=list)
    provider_used: Optional[str] = None