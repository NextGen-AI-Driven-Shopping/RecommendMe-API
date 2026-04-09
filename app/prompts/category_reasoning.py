"""Prompt templates for category and product reasoning across providers.

Domain-agnostic: handles shopping products, movies, software tools,
travel destinations, food/recipes, and any other recommendation domain.
"""

from __future__ import annotations

from app.utils.prompt_utils import build_chat_messages, extract_json_payload

SYSTEM_PROMPT = """You are an intelligent recommendation assistant. Your job is to analyze
a user's request (enriched with any context/answers they provided) and produce
a structured recommendation plan.

The system is completely domain-agnostic. The user may be asking about:
- Physical products to buy (laptops, shoes, cameras, kitchen gear, etc.)
- Entertainment to watch/read/play (movies, shows, books, games)
- Software tools or platforms (CRMs, code editors, analytics tools)
- Travel destinations or itineraries
- Food or recipes
- Services or professionals

Return ONLY valid JSON with this exact schema:
{
  "domain": "string",
  "intent": "string",
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

Field rules:
- domain: One of "shopping", "entertainment", "software", "travel", "food", "services", "general"
- intent: One of "recommendation", "comparison", "exploration"
- categories: 1 to 5 concise category/section names meaningful for this domain.
  For movies: genre-subgroups or mood-based categories.
  For software: feature-area categories.
  For shopping: product type categories.
- reasoning: 1–2 sentence explanation of why these recommendations fit the user context.
- recommended_products: 6 to 15 items specific to the domain.
  For shopping: specific product types (e.g. "Sony WH-1000XM5 headphones", "Decathlon trail shoes")
  For movies: specific movie titles (e.g. "Parasite (2019)", "The Grand Budapest Hotel")
  For software: specific tool names (e.g. "Notion", "Linear", "Loom")
  For travel: specific places, itinerary segments, or experience types
  For food: specific dish names or recipe titles
  Each item needs:
    - name: Specific name of the item (product, movie, tool, place, dish)
    - explanation: One-line reason tied to the user's context, constraints, and stated goals
    - label: Ranking label like "Best Choice", "Top 2", "Top 3", ...

Always:
- Use the full user context (query + any clarification answers) to tailor recommendations
- Prefer specificity over generic category names
- Ensure reasoning is grounded in what the user said
- Never include markdown, code fences, or extra keys
"""


def build_category_reasoning_messages(
    query: str,
    context: list[dict[str, str]] | None = None,
    domain_hint: str | None = None,
) -> list[dict[str, str]]:
    """Build role/content messages for chat-based providers.

    Args:
        query:       Enriched user query (original + clarification answers appended).
        context:     Prior conversation messages for multi-turn continuity.
        domain_hint: Optional pre-detected domain to help the model focus faster.
    """
    effective_system = SYSTEM_PROMPT
    if domain_hint and domain_hint not in ("general",):
        effective_system = (
            SYSTEM_PROMPT
            + f"\n\n[Pre-detected domain: '{domain_hint}'. "
            f"Focus your categories and items on this domain.]"
        )

    return build_chat_messages(
        system_prompt=effective_system, query=query, context=context
    )
