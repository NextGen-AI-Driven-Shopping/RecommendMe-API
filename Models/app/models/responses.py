"""
Request models for the RecommendMe API.

Defines the structure of the incoming data for the /v1/query endpoint,
including support for multi-turn conversation history.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class ConversationMessage(BaseModel):
    """
    A single message in the chat history.
    Compatible with OpenAI, Groq, and Gemini message formats.
    """
    role: str = Field(
        ..., 
        pattern="^(user|assistant|system)$",
        description="The role of the message sender: 'user' or 'assistant'."
    )
    content: str = Field(
        ..., 
        min_length=1, 
        description="The text content of the message."
    )


class QueryRequest(BaseModel):
    """
    The main input model for a recommendation query.
    """
    session_id: str = Field(
        ..., 
        description="Unique UUID or string to track the user's session."
    )
    user_message: str = Field(
        ..., 
        min_length=3, 
        description="The new message or search query from the user."
    )
    conversation_history: List[ConversationMessage] = Field(
        default_factory=list,
        description="The list of previous messages to provide context to the AI."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "550e8400-e29b-41d4-a716-446655440000",
                "user_message": "Make them waterproof",
                "conversation_history": [
                    {"role": "user", "content": "I need trekking shoes"},
                    {"role": "assistant", "content": "I found some great trekking shoes for you!"}
                ]
            }
        }