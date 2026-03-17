"""
app.models — Public re-exports for all Pydantic models.

Usage::

    from app.models import QueryRequest, QueryResponse, ProductCard
"""

from app.models.requests import ConversationMessage, QueryRequest
from app.models.responses import (
    CategoryResult,
    ErrorResponse,
    FollowUpResponse,
    ProductCard,
    QueryResponse,
    RecommendationResponse,
)
from app.models.internal import (
    ExtractedIntent,
    ProductSearchQuery,
    RankedProduct,
    VaguenessResult,
)

__all__ = [
    # Requests
    "ConversationMessage",
    "QueryRequest",
    # Responses
    "CategoryResult",
    "ErrorResponse",
    "FollowUpResponse",
    "ProductCard",
    "QueryResponse",
    "RecommendationResponse",
    # Internal
    "ExtractedIntent",
    "ProductSearchQuery",
    "RankedProduct",
    "VaguenessResult",
]
