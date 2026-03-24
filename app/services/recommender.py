"""
Recommendation intent and category extraction service.

Tier 2 AI: uses GPT-4o to parse the user query into structured intent
and produce a list of search categories used for the SerpAPI fetch step.
"""

import json
import time
from openai import OpenAI
from app.prompts.intent_extraction import build_intent_prompt
from app.models.internal import IntentResult

from app.services.cache import (
    get_cached_result,
    set_cached_result,
    build_cache_key
)

client = OpenAI()


async def extract_intent(
    query: str,
    context: list | None = None,
) -> IntentResult:
    """
    Args:
        query:   The clarified user query string.
        context: Optional conversation history for richer context.

    Returns:
        IntentResult containing the refined query, category list,
        and any extracted product attributes (budget, brand, etc.).
    """

    # Create cache key
    cache_key = build_cache_key(query)

    # Check cache
    cached = await get_cached_result(cache_key)
    if cached:
        print("[CACHE HIT]")
        return cached

    start_time = time.time()

    # Build prompt
    prompt = build_intent_prompt(query)

    # Call GPT
    response = client.chat.completions.create(
        model="gpt-4o",
        temperature=0.3,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": "Extract product recommendation categories from the query."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    # Parse response
    data = json.loads(response.choices[0].message.content)

    duration = time.time() - start_time

    if duration > 4:
        print(f"[WARN] Intent extraction took {duration:.2f}s")

    # Create result
    result = IntentResult(
        query=query,
        categories=data.get("categories", []),
        budget=data.get("budget", None),
        attributes=data
    )

    # Save to cache
    await set_cached_result(cache_key, result)

    return result