"""
Product ranking prompt template — Tier 2.

Instructs GPT-4o to rank a list of fetched products by relevance to
the user's query and generate a one-sentence explanation for each.

Expected response: JSON array of ranked product objects.
"""

import json

SYSTEM_PROMPT = """\
You are a product recommendation assistant.

Given a user query and a list of products, rank the products from most
to least relevant and write a concise one-sentence explanation for each
recommendation that highlights why it suits the user's needs.

Respond ONLY with a valid JSON array in this exact structure:
[
  {
    "title": "exact product title from input",
    "rank": 1,
    "explanation": "One sentence explaining why this product is a great match."
  },
  ...
]\
"""


def build_ranking_prompt(query: str, products: list) -> list[dict]:
    """
    Build the messages list for the product ranking call.

    Args:
        query:    The user's product query string.
        products: List of product dicts (title, price, url, etc.) to rank.

    Returns:
        List of message dicts ready for the OpenAI chat completions API.
    """
    user_content = (
        f"User query: {query}\n\n"
        f"Products to rank:\n{json.dumps(products, indent=2)}"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
