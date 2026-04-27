"""
Response models for the RecommendMe API.

Aligned to Flow.md — defines the shape of every outbound JSON response.
"""

from typing import List, Literal, Optional, Union

from pydantic import BaseModel, Field


# ── Product Item Response ────────────────────────────────────────────────────


class ProductItemResponse(BaseModel):
    """A single product item from SERP, shown as a card."""

    product_name: str
    image_url: str = ""
    price_inr: str = ""
    short_description: str = ""
    buy_link: str = ""
    rating: Optional[float] = None
    brand: Optional[str] = None
    reviews_count: Optional[int] = None
    delivery_info: Optional[str] = None
    availability: Optional[str] = None
    source: Optional[str] = None


# ── Product Type Response ────────────────────────────────────────────────────


class ProductTypeResponse(BaseModel):
    """A functional product class with its description and SERP-sourced items."""

    product_type: str
    description: str = ""
    product_items: List[ProductItemResponse] = Field(default_factory=list)
    serp_error: bool = False
    serp_error_message: Optional[str] = None


# ── Question with Options ────────────────────────────────────────────────────


class QuestionOptionResponse(BaseModel):
    """A follow-up question with optional selectable answer options."""

    question: str
    options: List[str] = Field(default_factory=list)


# ── Query Response ───────────────────────────────────────────────────────────


class QueryResponse(BaseModel):
    """
    Response body for POST /v1/query.

    Covers all pipeline states: clarification, recommendations, out of scope.
    """

    status: Literal[
        "clarification_needed",
        "recommendations",
        "out_of_scope",
        "pre_clarification",
        "error",
    ] = Field(..., description="Current pipeline state.")

    # ── Clarification fields ──
    message: Optional[str] = Field(
        None,
        description="Message for the user (clarification prompt, error, or out-of-scope explanation).",
    )
    questions: Optional[List[QuestionOptionResponse]] = Field(
        None,
        description="Follow-up questions with selectable options.",
    )
    clarification_round: Optional[int] = Field(
        None,
        description="1 for Round 1 (3 questions), 2 for Round 2 (2 questions), 0 for pre-clarification.",
    )
    asked_questions: Optional[int] = Field(
        None,
        description="Number of Q&A pairs gathered so far.",
    )
    max_total_questions: Optional[int] = Field(
        None,
        description="Always 5 per Flow.md.",
    )

    # ── Recommendation fields ──
    category: Optional[str] = Field(
        None,
        description="Display-only category label. Exactly 1 per session.",
    )
    product_types: Optional[List[ProductTypeResponse]] = Field(
        None,
        description="Product type sections with SERP-sourced items.",
    )
    summary: Optional[str] = Field(
        None,
        description="AI reasoning summary shown above the product list.",
    )

    # ── Session tracking ──
    session_id: Optional[str] = None


# ── Sufficiency Check Response ───────────────────────────────────────────────


class SufficiencyCheckResponse(BaseModel):
    """Response body for POST /v1/query/sufficiency_check."""

    sufficient: bool
    score: float
    asked_questions: int
    max_total_questions: int
    next_questions: List[QuestionOptionResponse] = Field(default_factory=list)
    clarification_round: int = Field(
        ...,
        description="1 for Round 1, 2 for Round 2.",
    )


# ── Health Response ──────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    """Response body for GET /v1/health."""

    status: str
    ollama: Optional[str] = None
    redis: Optional[str] = None
    openai: Optional[str] = None
    gemini: Optional[str] = None
    groq: Optional[str] = None
    serpapi: Optional[str] = None


# ── Auth Models ──────────────────────────────────────────────────────────────


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


# ── Session Models ───────────────────────────────────────────────────────────


class ChatMessageState(BaseModel):
    """Serialized message stored in a backend session snapshot."""

    id: str
    role: Literal["user", "assistant"]
    content: str
    type: Optional[Literal["followup", "recommendations", "text", "pre_clarification", "out_of_scope"]] = None
    questions: Optional[List[QuestionOptionResponse]] = None
    summary: Optional[str] = None
    category: Optional[str] = None
    product_types: Optional[List[ProductTypeResponse]] = None
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
    pending_questions: Optional[List[QuestionOptionResponse]] = None
    clarification_round: Optional[int] = None
    clarification_answers: Optional[List[dict]] = None
    latest_response: Optional[QueryResponse] = None
    feedback_count: int = 0
    saved_count: int = 0


class SessionFeedbackResponse(BaseModel):
    """Response body for recommendation feedback logging."""

    session_id: str
    message: str
    feedback_count: int


class SessionSaveResponse(BaseModel):
    """Response body for saving a recommendation snapshot."""

    session_id: str
    message: str
    saved_count: int


# ── Profile Models ───────────────────────────────────────────────────────────


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


# ── Chat Mode ────────────────────────────────────────────────────────────────


class ChatModeResponse(BaseModel):
    """Response body for POST /v1/chat/mode.

    Includes the AI answer text plus the full session product_types so the
    frontend can render product cards alongside the text response.
    """

    session_id: str
    message: str
    product_types: Optional[List[ProductTypeResponse]] = None
    category: Optional[str] = None