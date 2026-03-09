"""
Recommendation intent and category extraction service.

Tier 2 AI: uses GPT-4o to parse the user query into structured intent
and produce a list of search categories used for the SerpAPI fetch step.
"""

from app.models.internal import IntentResult


async def extract_intent(
    query: str,
    context: list | None = None,
) -> IntentResult:
    """
    Extract product intent and search categories from a user query.

    Args:
        query:   The clarified user query string.
        context: Optional conversation history for richer context.

    Returns:
        IntentResult containing the refined query, category list,
        and any extracted product attributes (budget, brand, etc.).
    """
    # TODO: call GPT-4o with the intent extraction prompt
    pass
