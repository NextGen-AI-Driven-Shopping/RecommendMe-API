"""
Intent extraction prompt template — Tier 2.

Instructs GPT-4o to parse a user query into structured product intent:
a refined query, up to three search categories, and key attributes
(budget, brand preference, use case, etc.).

Expected response: JSON conforming to IntentResult structure.
"""

SYSTEM_PROMPT = """\
You extract structured shopping intent from a user query.

Return ONLY valid JSON. No explanations.

Rules:
- "categories" must contain 1–3 product search categories.
- Categories must be short Google Shopping search phrases.
- If an attribute is unknown, return null.
- Do not invent details.

JSON schema:
{
  "refined_query": "clear rewritten shopping query",
  "categories": ["category1", "category2"],
  "attributes": {
    "budget": null,
    "use_case": null,
    "brand": null,
    "features": null
  }
}

Attribute rules:
- budget: price constraint if mentioned
- use_case: what the product will be used for
- brand: preferred brand if stated
- features: important product features

Return JSON only.
"""


def build_intent_prompt(query: str, context: list | None = None) -> list[dict]:
    """
    Build the messages list for the intent extraction call.

    Args:
        query:   The clarified user query string.
        context: Optional prior conversation messages in OpenAI format.

    Returns:
        List of message dicts ready for the OpenAI chat completions API.
    """
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    if context:
        messages.extend(context)
    messages.append({"role": "user", "content": query})
    return messages
