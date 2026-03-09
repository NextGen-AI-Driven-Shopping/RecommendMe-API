"""
Vagueness check prompt template — Tier 1.

Instructs the AI to classify a user query as CLEAR or VAGUE.
Expected response: exactly one word, either "CLEAR" or "VAGUE".
"""

SYSTEM_PROMPT = """\
You are a query classification assistant.

Your task is to determine whether a user's product search query contains
enough context to generate useful product recommendations.

Respond with exactly one word:
  CLEAR  — the query is specific enough to recommend products.
  VAGUE  — the query needs more context before recommendations can be made.

Do not include any other text, punctuation, or explanation.\
"""


def build_vagueness_prompt(query: str, context: list | None = None) -> list[dict]:
    """
    Build the messages list for the vagueness classification call.

    Args:
        query:   The user's raw query string.
        context: Optional prior conversation messages in OpenAI format.

    Returns:
        List of message dicts ready for the OpenAI chat completions API.
    """
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    if context:
        messages.extend(context)
    messages.append({"role": "user", "content": query})
    return messages
