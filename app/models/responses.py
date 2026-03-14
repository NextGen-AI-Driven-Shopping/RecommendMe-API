"""
Response models for the RecommendMe API.

Defines the shape of every outbound JSON response served by the API.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, HttpUrl


class ProductCard(BaseModel):
    """A single product recommendation card."""

    title: str
    price: Optional[str] = None
    url: HttpUrl
    image_url: Optional[str] = None
    source: Optional[str] = None
    rating: Optional[float] = None
    explanation: Optional[str] = None


class CategoryResult(BaseModel):
    """Ranked product recommendations grouped under a single category."""

    category: str
    products: List[ProductCard]


class QueryResponse(BaseModel):
    """Response body for POST /v1/query."""

    status: Literal["recommendations", "clarification_needed"] = Field(
        ...,
        description="'recommendations' or 'clarification_needed'",
    )
    message: Optional[str] = Field(
        None,
        description="Clarification prompt returned when the query is vague.",
    )
    categories: Optional[List[CategoryResult]] = None
    session_id: Optional[str] = None


class HealthResponse(BaseModel):
    """Response body for GET /v1/health."""

    status: str
    ollama: Optional[str] = None
    redis: Optional[str] = None
    openai: Optional[str] = None
    gemini: Optional[str] = None
    groq: Optional[str] = None
    serpapi: Optional[str] = None
