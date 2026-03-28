"""
Internal Pydantic models.

These types are used exclusively for inter-service communication
inside the application and are never serialized into API responses.
"""

from typing import List, Optional
from pydantic import BaseModel, Field # Moved Field here for cleanliness


# ---------------------------------------------------------------------------
# Tier 1 & 2 AI Outputs
# ---------------------------------------------------------------------------

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
    follow_ups: Optional[List[str]] = None


# ---------------------------------------------------------------------------
# User & Authentication — Database Models
# ---------------------------------------------------------------------------

class UserInternal(BaseModel):
    """
    Internal representation of a user in the database.
    
    This includes sensitive fields like hashed_password that are 
    never sent back to the user/frontend.
    """
    id: str = Field(..., description="Unique UUID for the user")
    email: str = Field(..., description="User's primary email address")
    full_name: str
    hashed_password: str = Field(..., description="The salted/hashed password string")
    is_active: bool = Field(default=True)
    created_at: str = Field(..., description="ISO timestamp of account creation")