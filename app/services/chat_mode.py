"""
Post-recommendation chat mode service (Step 8 of Flow.md).

Handles follow-up questions after recommendations are displayed.
Passes full context per Flow.md:
  - Initial user query
  - All 5 follow-up questions and responses
  - Generated category and all Product Type descriptions
  - All product items data from SERP
  - User profile data
"""

from __future__ import annotations

import json
from typing import Any

from app.core.logger import get_logger
from app.services.vagueness import _try_provider_chain

logger = get_logger(__name__)


CHAT_SYSTEM_PROMPT = """\
You are a helpful product recommendation assistant in follow-up chat mode.

The user has already received product recommendations. They are now asking \
follow-up questions about those recommendations.

You have access to the full conversation context including:
- The user's original query
- All clarification Q&A pairs
- The category and product types that were recommended
- All product items with their prices, ratings, and descriptions

────────────────────────────────────────────
RULES
────────────────────────────────────────────
1. Answer ONLY based on the provided product data — never hallucinate products, \
   prices, or features.
2. When comparing products, reference their actual prices, ratings, and features.
3. If the user asks about a product not in the recommendations, say so honestly.
4. Keep responses concise and helpful.
5. If asked to recommend something new/different, suggest they start a new search.
6. Use a natural conversational tone.
7. Reference specific product names and details from the data when relevant.
"""


def _build_context_message(
    *,
    original_query: str | None = None,
    clarification_answers: list[dict[str, str]] | None = None,
    category: str | None = None,
    product_types_data: list[dict] | None = None,
    user_profile: dict | None = None,
) -> str:
    """Build a comprehensive context string from all session data."""
    parts: list[str] = []

    if original_query:
        parts.append(f"Original query: \"{original_query}\"")

    if clarification_answers:
        parts.append("\nClarification Q&A:")
        for qa in clarification_answers:
            parts.append(f"  Q: {qa.get('question', '')}")
            parts.append(f"  A: {qa.get('answer', '')}")

    if category:
        parts.append(f"\nRecommendation category: {category}")

    if product_types_data:
        parts.append("\nRecommended product types:")
        for pt_data in product_types_data:
            pt_name = pt_data.get("product_type", "Unknown")
            pt_desc = pt_data.get("description", "")
            parts.append(f"\n--- {pt_name} ---")
            if pt_desc:
                parts.append(f"Description: {pt_desc}")

            items = pt_data.get("product_items", pt_data.get("products", []))
            if items:
                parts.append("Products:")
                for i, item in enumerate(items[:10], 1):
                    # Handle both old and new format
                    name = item.get("product_name") or item.get("title", "Unknown")
                    price = item.get("price_inr") or item.get("price", "N/A")
                    rating = item.get("rating", "N/A")
                    source = item.get("source", "")
                    buy_link = item.get("buy_link") or item.get("url", "")
                    desc = item.get("short_description") or item.get("explanation", "")

                    parts.append(f"  {i}. {name} — {price}")
                    if rating and rating != "N/A":
                        parts.append(f"     Rating: {rating}/5")
                    if source:
                        parts.append(f"     Source: {source}")
                    if desc:
                        parts.append(f"     {desc}")
                    if buy_link:
                        parts.append(f"     Link: {buy_link}")

    if user_profile:
        profile_parts = []
        if user_profile.get("gender"):
            profile_parts.append(f"Gender: {user_profile['gender']}")
        if user_profile.get("age"):
            profile_parts.append(f"Age: {user_profile['age']}")
        if user_profile.get("interests"):
            interests = user_profile["interests"]
            if isinstance(interests, list):
                interests = ", ".join(interests)
            profile_parts.append(f"Interests: {interests}")
        if profile_parts:
            parts.append(f"\nUser profile: {'; '.join(profile_parts)}")

    return "\n".join(parts)


async def answer_chat_followup(
    *,
    question: str,
    session_data: dict | None = None,
    categories_payload: list[dict] | None = None,
    profile_context: dict | None = None,
) -> str:
    """
    Generate an answer to a follow-up question in chat mode.

    Per Flow.md Step 8, passes full context:
    - Original query + all Q&As
    - Category + all Product Type descriptions
    - All product items from SERP
    - User profile

    Args:
        question: The user's follow-up question.
        session_data: Full session data dict (contains all context).
        categories_payload: Legacy categories payload for backward compat.
        profile_context: User profile data.

    Returns:
        AI-generated answer string.
    """
    # Build context from session data (new format)
    if session_data:
        context = _build_context_message(
            original_query=session_data.get("original_query"),
            clarification_answers=session_data.get("clarification_answers"),
            category=session_data.get("category"),
            product_types_data=session_data.get("product_types", []),
            user_profile=profile_context,
        )
    elif categories_payload:
        # Legacy backward compat: categories_payload is a list of category dicts
        context = _build_context_message(
            product_types_data=categories_payload,
            user_profile=profile_context,
        )
    else:
        context = "No product data available."

    messages = [
        {"role": "system", "content": CHAT_SYSTEM_PROMPT},
        {"role": "user", "content": f"PRODUCT CONTEXT:\n{context}\n\nUSER QUESTION: {question}"},
    ]

    raw = await _try_provider_chain(messages, step_name="chat_mode")

    if not raw:
        logger.warning("Chat mode: all providers failed for question=%s", question[:80])
        return (
            "I'm having trouble processing your question right now. "
            "Please try again in a moment, or start a new search for different products."
        )

    return raw.strip()
