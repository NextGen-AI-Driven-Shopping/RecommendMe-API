"""
Response models for the RecommendMe API.

Defines the shape of every outbound JSON response served by the API.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class ProductCard(BaseModel):
    """A single product recommendation card."""

    title: str
    price: Optional[str] = None
    url: str
    image_url: Optional[str] = None
    source: Optional[str] = None
    rating: Optional[float] = None
    reviews: Optional[int] = None
    explanation: Optional[str] = None
    label: Optional[str] = None


class CategoryResult(BaseModel):
    """Ranked product recommendations grouped under a single category."""

    category: str
    tagline: Optional[str] = None
    why_needed: Optional[str] = None
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
    questions: Optional[List[str]] = Field(
        None,
        description="List of specific follow-up questions for the user.",
    )
    summary: Optional[str] = Field(
        None,
        description="AI reasoning summary shown to the user above the product list.",
    )
    categories: Optional[List[CategoryResult]] = None
    session_id: Optional[str] = None
    clarification_round: Optional[int] = Field(
        None,
        description="Clarification stage index: 1 for initial 3 questions, 2 for additional stage.",
    )
    asked_questions: Optional[int] = Field(
        None,
        description="Number of clarification Q&A pairs gathered so far.",
    )
    max_total_questions: Optional[int] = Field(
        None,
        description="Configured maximum clarification question count.",
    )
    sufficiency_score: Optional[float] = Field(
        None,
        description="Confidence score in [0,1] indicating whether user intent is sufficiently specified.",
    )


class SufficiencyCheckResponse(BaseModel):
    """Response body for POST /v1/query/sufficiency_check."""

    sufficient: bool
    score: float
    asked_questions: int
    max_total_questions: int
    next_questions: List[str] = Field(default_factory=list)
    clarification_round: int = Field(
        ...,
        description="1 for initial stage, 2 when additional targeted questions are returned.",
    )


class HealthResponse(BaseModel):
    """Response body for GET /v1/health."""

    status: str
    ollama: Optional[str] = None
    redis: Optional[str] = None
    openai: Optional[str] = None
    gemini: Optional[str] = None
    groq: Optional[str] = None
    serpapi: Optional[str] = None


class AuthUser(BaseModel):
    """Public auth user profile returned to frontend."""

    user_id: str
    username: str
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    created_at: str


class AuthSignupResponse(BaseModel):
    """Response body for POST /v1/auth/signup."""

    message: str
    token: str
    user: AuthUser


class AuthLoginResponse(BaseModel):
    """Response body for POST /v1/auth/login."""

    message: str
    token: str
    user: AuthUser
