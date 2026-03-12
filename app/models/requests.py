"""
Request models for the RecommendMe API.

Used to validate and parse all incoming HTTP request bodies.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class ConversationMessage(BaseModel):
    """A single message in a multi-turn conversation."""

    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., description="Message content.")


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
        description="Prior conversation messages for multi-turn context.",
    )
