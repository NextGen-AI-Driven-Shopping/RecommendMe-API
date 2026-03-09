"""
Intent extraction prompt template — Tier 2.

Instructs GPT-4o to parse a user query into structured product intent:
a refined query, up to three search categories, and key attributes
(budget, brand preference, use case, etc.).

Expected response: JSON conforming to IntentResult structure.
"""

SYSTEM_PROMPT = """\
You are a product intent extraction assistant.

Given a user query (and optional conversation history for context), extract:
  1. A refined, unambiguous version of the query.
  2. Up to 3 specific product search categories
     (e.g. "wireless headphones", "noise-cancelling earbuds").
  3. Key product attributes the user cares about
     (budget, brand, use case, colour, compatibility, etc.).

Respond ONLY with valid JSON in this exact structure:
{
  "refined_query": "...",
  "categories": ["...", "..."],
  "attributes": {
    "budget": "...",
    "use_case": "..."
  }
}\
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
