"""
Query route handler — POST /v1/query.

Core recommendation endpoint.  Accepts a user query with optional
conversation history, runs vagueness detection, and returns either
ranked product recommendations or a clarification prompt.
"""

from fastapi import APIRouter, Depends

from app.api.deps import get_session
from app.models.requests import QueryRequest
from app.models.responses import QueryResponse

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def handle_query(
    payload: QueryRequest,
    session: dict = Depends(get_session),
) -> QueryResponse:
    """
    Process a product recommendation query.

    Flow:
      1. Validate and sanitize input.
      2. Classify query vagueness (Tier 1 AI).
      3. If vague, return a clarification prompt.
      4. Extract intent and categories (Tier 2 AI).
      5. Fetch products via SerpAPI.
      6. Rank products and generate explanations (Tier 2 AI).
      7. Return ranked CategoryResult list.
    """
    # TODO: implement full pipeline
    pass
