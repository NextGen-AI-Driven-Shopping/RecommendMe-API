"""
Recommendation intent and category extraction service.

Tier 2 AI: uses GPT-4o to parse the user query into structured intent
and produce a list of search categories used for the SerpAPI fetch step.
"""

from app.models.internal import IntentResult
import json
import time
from openai import OpenAI
from app.prompts.intent_extraction import build_intent_prompt

client = OpenAI()


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
    Extract product intent and search categories from a user query.

   
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

    return IntentResult(
        query=query,
        categories=data.get("categories", []),
        budget=data.get("budget", None),
        attributes=data
    )
