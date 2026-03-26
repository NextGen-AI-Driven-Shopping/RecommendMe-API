"""Prompt templates for category and product reasoning across providers."""

from __future__ import annotations

from app.utils.prompt_utils import build_chat_messages, extract_json_payload

SYSTEM_PROMPT = """You are a shopping assistant that transforms a user query into structured output.
Return only valid JSON with this exact schema:
{
  "categories": ["string"],
  "reasoning": "string",
  "recommended_products": [
    {
      "name": "string",
      "explanation": "string",
      "label": "string"
    }
  ]
}
Rules:
- categories must include 1 to 5 concise shopping categories.
- recommended_products must include 3 to 8 specific products. Each product needs:
  - name: Specific product type name
  - explanation: Short explanation of why it fits the user
  - label: E.g., "Best Pick", "Runner Up", "AI Top Pick", or "Other"
- reasoning must be concise and grounded in the query context.
- Never include markdown, code fences, or extra keys.
"""


def build_category_reasoning_messages(
    query: str,
    context: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    """Build role/content messages for chat-based providers."""
    return build_chat_messages(system_prompt=SYSTEM_PROMPT, query=query, context=context)
