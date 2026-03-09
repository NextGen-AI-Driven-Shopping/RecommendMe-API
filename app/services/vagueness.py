"""
Vagueness detection service.

Tier 1 AI check: determines whether a user query contains sufficient
context to generate product recommendations without further clarification.

Strategy:
  1. Attempt classification using the local Ollama model (fast, free).
  2. Fall back to GPT-4o-mini if Ollama is unavailable or times out.

Returns:
  "CLEAR"  — query has enough context for recommendations.
  "VAGUE"  — query needs a follow-up clarification question.
"""

from app.models.internal import VaguenessResult


async def classify_vagueness(
    query: str,
    context: list | None = None,
) -> VaguenessResult:
    """
    Classify a query as CLEAR or VAGUE.

    Args:
        query:   The raw user query string.
        context: Optional list of prior conversation messages.

    Returns:
        VaguenessResult with classification and optional follow-up question.
    """
    # TODO: implement Ollama call with GPT-4o-mini fallback
    pass


async def _call_ollama(prompt_messages: list) -> str:
    """Send a prompt to the local Ollama instance and return the response text."""
    pass


async def _call_openai_fallback(prompt_messages: list) -> str:
    """Send a prompt to GPT-4o-mini as a fallback and return the response text."""
    pass
