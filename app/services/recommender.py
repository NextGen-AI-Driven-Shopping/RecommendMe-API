"""
Recommendation plan generation service (Step 5 of Flow.md).

Generates the recommendation plan from AI: exactly 1 category + up to 10
Product Types with context-aware descriptions.

NO product names are generated here — those come from SERP in Step 6.
"""

from __future__ import annotations

import json
from typing import Any

from app.core.logger import get_logger
from app.models.internal import ProductType, RecommendationResult
from app.prompts.category_reasoning import build_recommendation_messages
from app.services.vagueness import _try_provider_chain
from app.utils.prompt_utils import extract_json_payload

logger = get_logger(__name__)


class RecommendationServiceError(Exception):
    """Raised when the recommendation plan cannot be generated."""


async def generate_recommendation_plan(
    query: str,
    *,
    conversation_context: list[dict[str, str]] | None = None,
    user_profile: dict[str, Any] | None = None,
) -> RecommendationResult:
    """
    Generate a recommendation plan from the AI.

    This corresponds to Flow.md Step 5:
    - Input: full unabridged conversation (query + all 5 Q&As + user profile)
    - Output: exactly 1 display-label Category + up to 10 Product Types

    Args:
        query: The consolidated query with all clarification context.
        conversation_context: Full conversation history.
        user_profile: User profile for personalization.

    Returns:
        RecommendationResult with category and product types (no items yet).

    Raises:
        RecommendationServiceError: If all providers fail.
    """
    messages = build_recommendation_messages(
        query=query,
        conversation_context=conversation_context,
        user_profile=user_profile,
    )

    raw = await _try_provider_chain(messages, step_name="recommendation_plan")
    if not raw:
        raise RecommendationServiceError(
            "All AI services failed to generate recommendations. Please try again."
        )

    try:
        payload = extract_json_payload(raw)
    except (ValueError, json.JSONDecodeError) as exc:
        logger.error(
            "Recommendation plan JSON parse failed: %s | raw=%s", exc, raw[:400]
        )
        raise RecommendationServiceError(
            "Failed to parse recommendation plan from AI."
        ) from exc

    # Extract category (exactly 1)
    category = str(payload.get("category", "Recommendations")).strip()
    if not category:
        category = "Recommendations"

    # Extract product types (up to 10)
    raw_types = payload.get("product_types", [])
    if not isinstance(raw_types, list):
        raw_types = []

    product_types: list[ProductType] = []
    for item in raw_types[:10]:
        if not isinstance(item, dict):
            continue

        pt_name = str(item.get("product_type", "")).strip()
        pt_desc = str(item.get("description", "")).strip()

        if not pt_name:
            continue

        product_types.append(
            ProductType(
                product_type=pt_name,
                description=pt_desc,
            )
        )

    if not product_types:
        logger.error("AI returned no valid product types | raw=%s", raw[:400])
        raise RecommendationServiceError(
            "AI failed to generate product type recommendations."
        )

    logger.info(
        "Recommendation plan generated: category=%s product_types=%d",
        category,
        len(product_types),
    )

    return RecommendationResult(
        category=category,
        product_types=product_types,
    )
