"""
Internal models for the RecommendMe API.

These types are *not* exposed to API consumers — they flow between
internal services (vagueness → recommender → products → ranking).
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Tier 1 AI output — vagueness classification
# ---------------------------------------------------------------------------

class VaguenessResult(BaseModel):
    """
    Output of the Tier 1 AI (Ollama / GPT-4o-mini fallback).

    Classifies whether the user's query has enough context to generate
    actionable product recommendations.
    """

    is_clear: bool = Field(
        ...,
        description="True if the query has enough context for recommendations.",
    )
    follow_up_questions: Optional[list[str]] = Field(
        default=None,
        description="Clarifying questions to ask if the query is vague.",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Model confidence in the classification (0–1).",
    )


# ---------------------------------------------------------------------------
# Tier 2 AI output — intent extraction
# ---------------------------------------------------------------------------

class ExtractedIntent(BaseModel):
    """
    Output of the Tier 2 AI (GPT-4o) intent-extraction step.

    Identifies every product category the user needs, derived from
    the original query plus any follow-up context.
    """

    original_query: str = Field(
        ...,
        description="The user's original unmodified query.",
    )
    resolved_context: str = Field(
        ...,
        description="Full context after merging query + follow-up answers.",
    )
    categories: list[str] = Field(
        ...,
        min_length=1,
        description="Product categories the user needs (e.g., ['Tent', 'Sleeping Bag']).",
    )


# ---------------------------------------------------------------------------
# Product search query — sent to SerpAPI
# ---------------------------------------------------------------------------

class ProductSearchQuery(BaseModel):
    """
    Search parameters built from an extracted intent category.

    One ``ProductSearchQuery`` is created per category and sent to SerpAPI.
    """

    category: str = Field(
        ...,
        description="The product category being searched.",
    )
    search_terms: list[str] = Field(
        ...,
        min_length=1,
        description="Keywords to search for on Google Shopping.",
    )
    max_price: Optional[float] = Field(
        default=None,
        ge=0,
        description="Upper price bound (in local currency).",
    )
    min_rating: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=5.0,
        description="Minimum acceptable rating.",
    )


# ---------------------------------------------------------------------------
# Post-ranking product — internal enrichment
# ---------------------------------------------------------------------------

class RankedProduct(BaseModel):
    """
    A product that has been through the GPT-4o ranking step.

    Extends the raw product data with a rank position and relevance score.
    """

    title: str
    price: str
    rating: float = Field(..., ge=0.0, le=5.0)
    reviews: str
    source: str
    link: str
    thumbnail: Optional[str] = None
    reason: str
    rank: int = Field(..., ge=1, description="Position in the ranking (1 = best).")
    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Relevance score from the ranking model (0–1).",
    )
    # ---------------------------------------------------------------------------
# User & Authentication — database models
# ---------------------------------------------------------------------------
class UserInternal(BaseModel):
    """
    Internal representation of a user in the database.
    
    Includes sensitive information like hashed_password that should 
    NEVER be returned to the frontend.
    """
    id: str = Field(..., description="Unique UUID for the user")
    email: str = Field(..., description="User's primary email address")
    full_name: str
    hashed_password: str = Field(..., description="The salted/hashed password string")
    is_active: bool = Field(default=True)
    created_at: str = Field(..., description="ISO timestamp of account creation")
