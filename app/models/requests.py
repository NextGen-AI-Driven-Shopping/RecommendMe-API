"""
Request models for the RecommendMe API.

Used to validate and parse all incoming HTTP request bodies.
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
    """Request body for POST /v1/query."""

    # The user's current message / search query.
    user_message: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="The user's product search query or conversational message.",
    )
    session_id: Optional[str] = Field(
        None,
        description="Session ID for conversation continuity across requests.",
    )
    # Full conversation history sent by the frontend for multi-turn context.
    conversation_history: Optional[List[ConversationMessage]] = Field(
        default_factory=list,
        max_length=20,
        description="Prior conversation messages for multi-turn context.",
    )
    # Answers to clarification questions
    clarification: Optional[List[ClarificationAnswer]] = Field(
        default_factory=list,
        description="List of clarification questions and user responses.",
    )

    @field_validator("user_message", mode="before")
    @classmethod
    def strip_user_message(cls, value: str) -> str:
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

    identifier: str = Field(..., min_length=3, max_length=120)
    password: str = Field(..., min_length=1, max_length=128)

    @field_validator("identifier", "password", mode="before")
    @classmethod
    def strip_login_fields(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value
