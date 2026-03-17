"""Prompt templates for category and product reasoning across providers."""

from __future__ import annotations

import json

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
    messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    if context:
        messages.extend(context)
    messages.append({"role": "user", "content": query})
    return messages


def extract_json_payload(text: str) -> dict:
    """Extract the first JSON object from model output and parse it."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model response")
    return json.loads(text[start : end + 1])
