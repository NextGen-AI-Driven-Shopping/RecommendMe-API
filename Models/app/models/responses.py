"""
Response models for the RecommendMe API.

Covers both possible return shapes from ``POST /v1/query``:
  - ``FollowUpResponse``  — when the query is vague
  - ``RecommendationResponse`` — when the query is clear

Also includes the unified ``ErrorResponse`` envelope.
"""

from __future__ import annotations

from typing import Literal, Optional, Union

from pydantic import BaseModel, Field, HttpUrl, field_validator


# ---------------------------------------------------------------------------
# Product & category models
# ---------------------------------------------------------------------------

class ProductCard(BaseModel):
    """A single product recommendation with live data."""

    title: str = Field(
        ...,
        min_length=1,
        max_length=300,
        description="Product title as it appears on the source platform.",
    )
    price: str = Field(
        ...,
        min_length=1,
        description="Formatted price string (e.g., '₹3,499').",
    )
    rating: float = Field(
        ...,
        ge=0.0,
        le=5.0,
        description="Average user rating (0–5).",
    )
    reviews: str = Field(
        ...,
        description="Review count as a formatted string (e.g., '2,140').",
    )
    source: str = Field(
        ...,
        min_length=1,
        description="Platform name (e.g., 'Amazon', 'Decathlon').",
    )
    link: HttpUrl = Field(
        ...,
        description="Direct purchase URL.",
    )
    thumbnail: Optional[HttpUrl] = Field(
        default=None,
        description="Product image URL.",
    )
    reason: str = Field(
        ...,
        min_length=1,
        description="AI-generated explanation of why this product fits the user's needs.",
    )


class CategoryResult(BaseModel):
    """
    A grouped set of recommendations for a single product category.

    Example: "Tent" with 3 product cards, a reason why it's needed,
    and an optional budget allocation hint.
    """

    name: str = Field(
        ...,
        min_length=1,
        description="Category name (e.g., 'Tent', 'Sleeping Bag').",
    )
    why_needed: str = Field(
        ...,
        min_length=1,
        description="AI-generated explanation of why this category is relevant.",
    )
    budget_allocation: Optional[str] = Field(
        default=None,
        description="Suggested price range for this category (e.g., '₹3,000 – ₹6,000').",
    )
    products: list[ProductCard] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="Top product picks in this category (1–5).",
    )
    expert_tip: Optional[str] = Field(
        default=None,
        description="Optional buying advice for this category.",
    )


# ---------------------------------------------------------------------------
# Top-level response shapes
# ---------------------------------------------------------------------------

class FollowUpResponse(BaseModel):
    """Returned when the user's query is too vague for recommendations."""

    type: Literal["followup"] = Field(
        default="followup",
        description="Discriminator — always 'followup'.",
    )
    questions: list[str] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="Targeted clarifying questions (1–5).",
    )

    @field_validator("questions", mode="after")
    @classmethod
    def strip_questions(cls, v: list[str]) -> list[str]:
        return [q.strip() for q in v if q.strip()]


class RecommendationResponse(BaseModel):
    """Returned when the query is clear — contains the final product picks."""

    type: Literal["recommendations"] = Field(
        default="recommendations",
        description="Discriminator — always 'recommendations'.",
    )
    summary: str = Field(
        ...,
        min_length=1,
        description="One-line summary of what was recommended and why.",
    )
    categories: list[CategoryResult] = Field(
        ...,
        min_length=1,
        description="Product categories with ranked picks.",
    )


# Discriminated union — the frontend checks `type` to decide what to render.
QueryResponse = Union[FollowUpResponse, RecommendationResponse]


# ---------------------------------------------------------------------------
# Error envelope
# ---------------------------------------------------------------------------

class ErrorResponse(BaseModel):
    """Standardized error response returned on all failure paths."""

    error: Literal[True] = Field(
        default=True,
        description="Always true for error responses.",
    )
    code: str = Field(
        ...,
        description="Machine-readable error code (e.g., 'QUERY_TOO_SHORT').",
    )
    message: str = Field(
        ...,
        description="Human-readable error description.",
    )
    retry_after: Optional[int] = Field(
        default=None,
        description="Seconds to wait before retrying (if applicable).",
    )
