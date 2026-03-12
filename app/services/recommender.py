"""
Recommendation intent and category extraction service — Tier 2 AI.

Calls GPT-4o with the intent extraction prompt to parse a user query into
a structured IntentResult containing:
  - refined_query  : a cleaner version of the original query.
  - categories     : 1–3 Google Shopping search phrases.
  - attributes     : optional budget, brand, use-case, and feature hints.

TODO: Implementation pending from recommender service owner.
      The function signature and return type are finalised.  Add the
      OpenAI async client call and JSON parsing logic below.
"""

import json

from app.core.config import get_settings
from app.core.logger import get_logger
from app.models.internal import IntentResult
from app.prompts.intent_extraction import build_intent_prompt

logger = get_logger(__name__)


async def extract_intent(
    query: str,
    context: list | None = None,
) -> IntentResult | None:
    """
    Extract product intent and search categories from a user query.

    Args:
        query:   The clarified user query string.
        context: Optional prior conversation messages in OpenAI message format
                 for richer multi-turn context.

    Returns:
        IntentResult containing the refined query, category list, and any
        extracted product attributes (budget, brand, etc.).
        Returns None if the AI service is unavailable or not yet configured.

    TODO: Implementation pending from recommender service owner.
          Replace the placeholder below with the real OpenAI async call.
    """
    settings = get_settings()

    if not settings.OPENAI_API_KEY:
        # Temporary placeholder until the OpenAI key is configured in .env
        logger.warning("OPENAI_API_KEY not set; extract_intent returning None.")
        return None

    # TODO: Implementation pending from module owner.
    #       1. Build the prompt using build_intent_prompt(query, context).
    #       2. Call openai.AsyncOpenAI().chat.completions.create(...).
    #       3. Parse the JSON response into IntentResult.
    #
    # Example skeleton (do not finalise until the service owner reviews):
    #
    #   try:
    #       import openai
    #       client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    #       messages = build_intent_prompt(query, context)
    #       response = await client.chat.completions.create(
    #           model="gpt-4o",
    #           messages=messages,
    #           temperature=0,
    #       )
    #       raw_json = response.choices[0].message.content
    #       data = json.loads(raw_json)
    #       return IntentResult(
    #           original_query=query,
    #           refined_query=data.get("refined_query", query),
    #           categories=data.get("categories", [query]),
    #           attributes=data.get("attributes"),
    #       )
    #   except Exception as exc:
    #       logger.error(f"extract_intent failed: {exc!r}")
    #       return None

    # Temporary placeholder until feature implementation is completed.
    return None
