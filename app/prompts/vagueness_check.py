"""
Vagueness check prompt template — Tier 1.

This prompt instructs the AI to classify a user query as CLEAR or VAGUE.
The model must return exactly one word: CLEAR or VAGUE.
"""

SYSTEM_PROMPT = """You are a query classification assistant.

Your task is to determine whether a user's product search query contains
enough context to generate useful product recommendations.

Respond with exactly one word:

CLEAR — the query is specific enough to recommend products.
VAGUE — the query needs more context before recommendations can be made.

Do not include any explanation or additional text.
"""


def build_vagueness_prompt(query: str, context: list | None = None) -> list[dict]:
    """
    Build messages for the LLM classification call.

    Args:
        query: user query
        context: optional previous conversation messages

    Returns:
        list of chat messages
    """

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]

    if context:
        messages.extend(context)

    messages.append(
        {"role": "user", "content": query}
    )

    return messages