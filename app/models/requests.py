"""
Request models for the RecommendMe API.

Aligned to Flow.md — validates all incoming HTTP request bodies.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class ConversationMessage(BaseModel):
    """A single message in a multi-turn conversation."""
    role: Literal["user", "assistant"] = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., min_length=1, max_length=2000, description="Message content.")

    @field_validator("content", mode="before")
    @classmethod
    def strip_content(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value


class ClarificationAnswer(BaseModel):
    """A single follow-up question and its answer."""
    question: str
    answer: str


class QueryRequest(BaseModel):
    """
    Request body for POST /v1/query.

    Supports the full Flow.md pipeline: initial query, pre-clarification,
    Round 1 (3 questions), Round 2 (2 questions), and final recommendation.
    """

    user_message: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="The user's query or conversational message.",
    )
    session_id: Optional[str] = Field(
        None,
        description="Session ID for conversation continuity across requests.",
    )
    request_id: Optional[str] = Field(
        None,
        description="Unique request ID to prevent duplicate processing.",
    )
    conversation_history: Optional[List[ConversationMessage]] = Field(
        default_factory=list,
        max_length=30,
        description="Prior conversation messages for multi-turn context.",
    )
    clarification: Optional[List[ClarificationAnswer]] = Field(
        default_factory=list,
        description="List of clarification questions and user responses.",
    )
    clarification_round: Optional[int] = Field(
        None,
        description="Current round: 0 for pre-clarification, 1 for Round 1 answers, 2 for Round 2 answers.",
    )

    @field_validator("user_message", mode="before")
    @classmethod
    def strip_user_message(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value


class ChatModeRequest(BaseModel):
    """Request body for post-results chat mode follow-up."""

    session_id: str = Field(..., min_length=1, max_length=120)
    user_message: str = Field(..., min_length=1, max_length=500)

    @field_validator("session_id", "user_message", mode="before")
    @classmethod
    def strip_chat_mode_fields(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value


class SufficiencyCheckRequest(BaseModel):
    """Request body for POST /v1/query/sufficiency_check."""

    user_message: str = Field(..., min_length=3, max_length=500)
    clarification: Optional[List[ClarificationAnswer]] = Field(default_factory=list)
    max_total_questions: int = Field(default=5, ge=3, le=5)

    @field_validator("user_message", mode="before")
    @classmethod
    def strip_sufficiency_user_message(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value


class SignupRequest(BaseModel):
    """Request body for POST /v1/auth/signup."""

    username: str = Field(..., min_length=2, max_length=100)
    first_name: str = Field(..., min_length=1, max_length=80)
    last_name: str = Field(..., min_length=1, max_length=80)
    email: Optional[str] = Field(default=None, max_length=120)
    phone: Optional[str] = Field(default=None, max_length=25)
    session_id: Optional[str] = Field(default=None, max_length=80)
    password: str = Field(..., min_length=6, max_length=128)

    @field_validator("username", "first_name", "last_name", mode="before")
    @classmethod
    def strip_name_fields(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("email", "phone", mode="before")
    @classmethod
    def strip_contact_fields(cls, value: Optional[str]) -> Optional[str]:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped if stripped else None
        return value

    @field_validator("password", mode="before")
    @classmethod
    def strip_password(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value


class LoginRequest(BaseModel):
    """Request body for POST /v1/auth/login."""

    identifier: Optional[str] = Field(default=None, max_length=120)
    password: Optional[str] = Field(default=None, max_length=128)
    session_id: Optional[str] = Field(default=None, max_length=80)

    @field_validator("identifier", "password", mode="before")
    @classmethod
    def strip_login_fields(cls, value: Optional[str]) -> Optional[str]:
        if isinstance(value, str):
            return value.strip()
        return value


class ForgotPasswordRequest(BaseModel):
    identifier: str = Field(..., min_length=3, max_length=120)

    @field_validator("identifier", mode="before")
    @classmethod
    def strip_identifier(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value


class ResetPasswordRequest(BaseModel):
    reset_token: str = Field(..., min_length=16, max_length=256)
    new_password: str = Field(..., min_length=6, max_length=128)

    @field_validator("reset_token", "new_password", mode="before")
    @classmethod
    def strip_reset_fields(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value


class ProfileUpdateRequest(BaseModel):
    username: Optional[str] = Field(default=None, min_length=2, max_length=100)
    gender: Optional[str] = Field(default=None, max_length=20)
    age: Optional[int] = Field(default=None, ge=13, le=120)
    interests: Optional[List[str]] = Field(default=None)
    about: Optional[str] = Field(default=None, max_length=1000)
    avatar_url: Optional[str] = Field(default=None, max_length=500)
    avatar_file_path: Optional[str] = Field(default=None, max_length=500)

    @field_validator("username", "gender", "about", "avatar_url", "avatar_file_path", mode="before")
    @classmethod
    def strip_optional_strings(cls, value: Optional[str]) -> Optional[str]:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped if stripped else None
        return value

    @field_validator("interests", mode="before")
    @classmethod
    def clean_interests(cls, value):
        if value is None:
            return None
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value
