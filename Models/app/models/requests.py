"""
Request models for the RecommendMe API.

These are the Pydantic schemas that validate incoming POST /v1/query payloads.
"""

from __future__ import annotations

from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class ConversationMessage(BaseModel):
    """A single message in the conversation history."""

    role: Literal["user", "assistant"] = Field(
        ...,
        description="Who sent this message.",
    )
    content: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The text content of the message.",
    )

    @field_validator("content", mode="before")
    @classmethod
    def strip_content(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v


class QueryRequest(BaseModel):
    """
    The primary request body for ``POST /v1/query``.

    * ``session_id`` is optional — the server generates one if absent.
    * ``conversation_history`` is capped at 20 messages to guard against
      prompt-injection and excessive context size.
    """

    session_id: Optional[UUID] = Field(
        default=None,
        description="Client-provided session ID. Server generates one if omitted.",
    )
    user_message: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="The user's current message in plain language.",
    )
    conversation_history: list[ConversationMessage] = Field(
        default_factory=list,
        max_length=20,
        description="Previous messages in this conversation (max 20).",
    )

    @field_validator("user_message", mode="before")
    @classmethod
    def strip_user_message(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v

    @model_validator(mode="after")
    def validate_message_word_count(self) -> "QueryRequest":
        """Ensure the user message has at least 3 words."""
        word_count = len(self.user_message.split())
        if word_count < 3:
            raise ValueError(
                f"Query must contain at least 3 words, got {word_count}."
            )
        return self

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "session_id": "550e8400-e29b-41d4-a716-446655440000",
                    "user_message": "I want to go trekking in Himachal Pradesh",
                    "conversation_history": [
                        {
                            "role": "user",
                            "content": "I want to go trekking",
                        }
                    ],
                }
            ]
        }
    }
