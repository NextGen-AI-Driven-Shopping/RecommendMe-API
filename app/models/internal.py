"""
Internal Pydantic models.

These types are used exclusively for inter-service communication
inside the application and are never serialized into API responses.
"""

from typing import List, Optional

from pydantic import BaseModel


class IntentResult(BaseModel):
    """Structured product intent extracted from a user query."""

    original_query: str
    refined_query: str
    categories: List[str]
    attributes: Optional[dict] = None


class VaguenessResult(BaseModel):
    """Result produced by the vagueness classification step."""

    classification: str  # "CLEAR" or "VAGUE"
    confidence: Optional[float] = None
    follow_up_question: Optional[str] = None
