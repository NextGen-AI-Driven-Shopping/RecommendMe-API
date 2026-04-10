"""
Response models for the RecommendMe API.

Defines the shape of every outbound JSON response served by the API.

Flow.md hierarchy:
    Category  (display label — exactly 1 per session)
      └── Product Type  (functional class — drives SERP query, max 10)
            └── Product Items  (real listings — fetched from SERP per Product Type, up to 10)
"""

from typing import List, Literal, Optional, Union

from pydantic import BaseModel, Field


class ProductCard(BaseModel):
    """A single product recommendation card sourced from SERP (never AI-generated)."""

    title: str
    """Product name from SERP — never AI-generated (Flow.md §37)."""

    price: Optional[str] = None
    """Price in INR. Required for card rendering."""

    url: str
    """Buy link — opens in new tab."""

    image_url: Optional[str] = None
    """Product image URL for card display."""

    source: Optional[str] = None
    """Source marketplace / retailer."""

    rating: Optional[float] = None
    """Star rating when available."""

    reviews: Optional[int] = None
    """Review count when available."""

    explanation: Optional[str] = None
    """Short description from listing or AI fallback."""

    label: Optional[str] = None
    """Rank label (e.g. 'Best Choice', 'Top 2')."""

    brand: Optional[str] = None
    """Brand name when available."""

    delivery_info: Optional[str] = None
    """Delivery information when available."""

    availability: Optional[str] = None
    """In stock / Out of stock when available."""


class ProductTypeResult(BaseModel):
    """One product type section with its SERP-fetched product items.

    Flow.md §Data Hierarchy:
    - product_type: functional class name — used as the SERP query basis.
    - description: unique 2–3 sentence context-aware explanation of WHY this
      product type is needed in the user's specific situation.
    - product_items: real-world listings fetched from SERP (up to 10).
    """

    product_type: str
    """Functional class name (e.g. 'Waterproof Trekking Shoes'). Used as SERP query."""

    description: str
    """Unique 2–3 sentence description specific to the user's context."""

    product_items: List[ProductCard] = Field(default_factory=list)
    """Real listings fetched from SERP (0–10). Empty when SERP failed for this type."""

    serp_failed: bool = False
    """True when SERP fetch failed for this product type. Frontend shows failure banner."""

    # ── Backward compat aliases ───────────────────────────────────────────────
    @property
    def products(self) -> List[ProductCard]:
        """Alias for product_items — used by legacy frontend normalizer."""
        return self.product_items

    @property
    def why_needed(self) -> str:
        """Alias for description — used by legacy frontend normalizer."""
        return self.description

    @property
    def category(self) -> str:
        """Alias for product_type — used by legacy frontend normalizer."""
        return self.product_type

    @property
    def tagline(self) -> Optional[str]:
        """Legacy compat — returns None."""
        return None


# ── Keep old name as alias so existing imports don't break ──────────────────
CategoryResult = ProductTypeResult


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

    # ── Flow.md canonical fields ───────────────────────────────────────────────
    category: Optional[str] = Field(
        None,
        description="Display label for the session — exactly 1 per session (Flow.md §21).",
    )
    product_types: Optional[List[ProductTypeResult]] = Field(
        None,
        description="Up to 10 product type sections, each with description + SERP items (Flow.md §27).",
    )

    # ── Backward compat — frontend still reads .categories ────────────────────
    # Populated by the route handler from product_types for old frontend code.
    categories: Optional[List[ProductTypeResult]] = Field(
        None,
        description="Legacy alias for product_types. Deprecated — use product_types instead.",
    )

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
    domain: Optional[str] = Field(
        None,
        description="Detected domain: 'shopping', 'entertainment', 'software', 'travel', 'food', 'services', 'general'.",
    )
    intent: Optional[str] = Field(
        None,
        description="Detected intent: 'recommendation', 'comparison', 'exploration'.",
    )
    # ── Data-source transparency fields ───────────────────────────────────────
    data_source: Optional[Literal["live", "llm_only", "unavailable"]] = Field(
        None,
        description=(
            "Indicates the origin of product data. "
            "'live'=real listings, 'llm_only'=ideas only, 'unavailable'=all sources failed."
        ),
    )
    degraded: Optional[bool] = Field(
        None,
        description="True when the response is partial or sourced from fallback/LLM only.",
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
    session_id: Optional[str] = None


class AuthLoginResponse(BaseModel):
    """Response body for POST /v1/auth/login."""

    message: str
    token: str
    user: AuthUser
    session_id: Optional[str] = None
    profile: Optional[dict] = None


class ChatMessageState(BaseModel):
    """Serialized message stored in a backend session snapshot."""

    id: str
    role: Literal["user", "assistant"]
    content: str
    type: Optional[Literal["followup", "recommendations", "text"]] = None
    questions: Optional[List[str]] = None
    summary: Optional[str] = None
    categories: Optional[List[ProductTypeResult]] = None
    timestamp: str


class ChatSessionState(BaseModel):
    """Chat session snapshot returned to the frontend for hydration."""

    session_id: str
    status: Literal["new", "clarification_needed", "recommendations"] = "new"
    title: str = "New Chat"
    user_id: Optional[str] = None
    messages: List[ChatMessageState] = Field(default_factory=list)
    created_at: str
    updated_at: str
    original_query: Optional[str] = None
    pending_questions: Optional[List[str]] = None
    current_question_index: Optional[int] = None
    clarification_answers: Optional[List[dict]] = None
    latest_response: Optional[QueryResponse] = None


class AvatarOption(BaseModel):
    id: str
    gender: str
    url: str


class UserProfile(BaseModel):
    user_id: str
    username: str
    email: str
    gender: str = "Other"
    age: Optional[int] = None
    interests: List[str] = Field(default_factory=list)
    about: str = ""
    avatar_url: str
    avatar_file_path: Optional[str] = None
    created_at: str
    updated_at: str


class ProfileResponse(BaseModel):
    profile: UserProfile


class AvatarOptionsResponse(BaseModel):
    avatars: List[AvatarOption]


class PasswordResetResponse(BaseModel):
    message: str
    reset_token: Optional[str] = None


class ChatModeResponse(BaseModel):
    """Response body for POST /v1/chat/mode."""

    session_id: str
    message: str
