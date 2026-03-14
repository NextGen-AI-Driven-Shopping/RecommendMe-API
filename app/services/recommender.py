"""AI orchestration service for category and product reasoning."""

from __future__ import annotations

from app.core.logger import get_logger
from app.models.internal import IntentResult
from app.providers import (
    BaseCategoryProvider,
    CategoryReasoningResult,
    GeminiProvider,
    GroqProvider,
    OllamaProvider,
    OpenAIProvider,
    ProviderError,
)

logger = get_logger(__name__)


class RecommendationServiceError(Exception):
    """Raised when every provider in the fallback chain fails."""


def _normalize_context(context: list | None) -> list[dict[str, str]]:
    """Normalize context payload into chat messages for providers."""
    if not context:
        return []

    normalized: list[dict[str, str]] = []
    for item in context:
        if isinstance(item, dict):
            role = item.get("role") or "user"
            content = item.get("content") or ""
        else:
            role = getattr(item, "role", "user") or "user"
            content = getattr(item, "content", "") or ""
        if not isinstance(content, str) or not content.strip():
            continue
        normalized.append({"role": str(role), "content": content.strip()})
    return normalized


async def generate_category_plan(
    query: str,
    context: list | None = None,
) -> CategoryReasoningResult:
    """Generate category reasoning using provider fallback order."""
    providers: list[BaseCategoryProvider] = [
        GeminiProvider(),
        GroqProvider(),
        OpenAIProvider(),
        OllamaProvider(),
    ]
    provider_context = _normalize_context(context)

    errors: list[str] = []
    for provider in providers:
        try:
            result = await provider.generate(query=query, context=provider_context)
            logger.info(
                "Category plan generated provider=%s categories=%d products=%d",
                provider.provider_name,
                len(result.categories),
                len(result.recommended_products),
            )
            return result
        except ProviderError as exc:
            logger.warning("Provider failed provider=%s error=%s", provider.provider_name, exc)
            errors.append(f"{provider.provider_name}: {exc}")
            continue

    raise RecommendationServiceError("All providers failed: " + " | ".join(errors))


async def extract_intent(
    query: str,
    context: list | None = None,
) -> IntentResult | None:
    """Backward-compatible wrapper that maps category plan to IntentResult."""
    try:
        plan = await generate_category_plan(query=query, context=context)
    except RecommendationServiceError as exc:
        logger.error("extract_intent failed: %s", exc)
        return None

    return IntentResult(
        original_query=query,
        refined_query=query,
        categories=plan.categories,
        attributes={
            "reasoning": plan.reasoning,
            "recommended_products": plan.recommended_products,
        },
    )
