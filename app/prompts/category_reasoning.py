"""
Prompt template for recommendation generation (Step 5 of Flow.md).

Instructs the AI to generate:
  - Exactly 1 display-label Category
  - Up to 10 Product Types with context-aware descriptions
  - NO product names (those come from SERP in Step 6)
"""

from __future__ import annotations

import json
from typing import Any

from app.utils.prompt_utils import extract_json_payload

SYSTEM_PROMPT = """\
You are a product recommendation engine. Given a user query and their complete \
conversation context, generate a structured recommendation plan.

────────────────────────────────────────────
OUTPUT FORMAT  (return ONLY valid JSON, zero markdown)
────────────────────────────────────────────
{
  "category": "A single display label for the recommendation group",
  "product_types": [
    {
      "product_type": "Functional class name (drives SERP search)",
      "description": "2-3 sentence description referencing the user's SPECIFIC context"
    }
  ]
}

────────────────────────────────────────────
RULES
────────────────────────────────────────────

CATEGORY:
- Exactly 1 category per session
- This is a human-readable grouping header (e.g. "Trekking Gear", "Home Office Setup")
- It has NO functional role in recommendation logic or SERP queries

PRODUCT TYPES:
- Up to 10 product types per session
- Each is a functional class of product the user actually needs
- The name drives a SERP search query — make it specific and searchable
- Examples: "Waterproof Trekking Shoes", "Offline GPS App", "Lightweight Rain Poncho"

DESCRIPTIONS (critical):
- Every description must be UNIQUE — no repeated phrasing across product types
- Must reference the user's ACTUAL context: terrain, mood, use case, group size,
  duration, weather, budget, etc.
- Length: 2-3 sentences maximum
- Tone: Helpful and conversational. No promotional language.
- PROHIBITED phrases: "a great option", "highly recommended", "perfect for",
  or any superlative that doesn't add information
- Each description must answer:
  1. Why is this product type needed in this user's specific situation?
  2. What role does it play in helping the user reach their goal?

WHAT YOU MUST NOT DO:
- Do NOT generate product names or brand names
- Do NOT generate prices or URLs
- Do NOT include markdown, code fences, or extra keys
- Do NOT use generic descriptions that could apply to any user

────────────────────────────────────────────
EXAMPLES
────────────────────────────────────────────

User context: Solo trek, 4 days, monsoon season, Western Ghats

{
  "category": "Monsoon Trekking Gear",
  "product_types": [
    {
      "product_type": "Waterproof Trekking Shoes",
      "description": "Monsoon trails in the Western Ghats stay wet and muddy for \
hours after rain stops. Waterproof shoes keep your feet dry while the deep lug \
sole maintains grip on slippery roots and loose gravel — conditions you will face \
consistently on a 4-day route here."
    },
    {
      "product_type": "Offline GPS App",
      "description": "Cell coverage disappears quickly on Western Ghats trails. An \
offline GPS app with pre-downloaded maps lets you navigate without any data \
connection — essential for a solo trekker who cannot afford to get disoriented."
    },
    {
      "product_type": "Lightweight Rain Poncho",
      "description": "Monsoon rain arrives without warning and can last for hours. A \
poncho covering both you and your pack removes the need for a separate rain cover \
and jacket, saving meaningful weight on a multi-day carry."
    }
  ]
}
"""


def build_recommendation_messages(
    query: str,
    conversation_context: list[dict[str, str]] | None = None,
    user_profile: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    """
    Build the message list for recommendation generation (Step 5).

    Args:
        query: The consolidated query including all Q&A context.
        conversation_context: Full conversation history.
        user_profile: User profile data for personalization.

    Returns:
        Ordered list of chat messages for any chat-completion API.
    """
    if not query or not query.strip():
        raise ValueError("query must be a non-empty string")

    messages: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]

    # Add conversation context if available
    if conversation_context:
        for msg in conversation_context:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if content.strip():
                messages.append({"role": role, "content": content.strip()})

    # Build the user prompt with all context
    user_content_parts = [f"User's request: \"{query}\""]

    if user_profile:
        profile_parts = []
        if user_profile.get("age"):
            profile_parts.append(f"Age: {user_profile['age']}")
        if user_profile.get("interests"):
            interests = user_profile["interests"]
            if isinstance(interests, list):
                interests = ", ".join(interests)
            profile_parts.append(f"Interests: {interests}")
        if user_profile.get("gender"):
            profile_parts.append(f"Gender: {user_profile['gender']}")
        if profile_parts:
            user_content_parts.append(f"\nUser profile: {'; '.join(profile_parts)}")

    user_content_parts.append(
        "\nGenerate the category and product types now. "
        "Remember: up to 10 product types, each with a unique context-aware description. "
        "Do NOT generate product names."
    )

    messages.append({"role": "user", "content": "\n".join(user_content_parts)})
    return messages
