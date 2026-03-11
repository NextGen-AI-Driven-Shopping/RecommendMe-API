"""
Vagueness check prompt template — Tier 1.

Instructs the AI to classify a user query as CLEAR or VAGUE.
Expected response: exactly one word, either "CLEAR" or "VAGUE".
"""

SYSTEM_PROMPT = """
You are an AI assistant that decides whether a user's shopping query
has enough information to recommend products.

Return ONLY one word:

CLEAR  - if the user mentions a product type and at least one detail
        like budget, use case, or feature.

VAGUE  - if the query is too general and needs more details.

Examples:

User: I want headphones
Answer: VAGUE

User: Gaming headphones under 5000
Answer: CLEAR

User: Suggest a tent
Answer: VAGUE

User: 2 person trekking tent under 6000
Answer: CLEAR

Respond with only CLEAR or VAGUE.
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
