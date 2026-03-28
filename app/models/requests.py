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
    question: str = Field(..., min_length=1, max_length=500)
    answer: str = Field(..., min_length=1, max_length=500)

    @field_validator("question", "answer", mode="before")
    @classmethod
    def strip_clarification_fields(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value

class QueryRequest(BaseModel):
    """Request body for POST /v1/query."""

    # The user's current message / search query.
    user_message: str = Field(
        ...,
        min_length=1,
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
