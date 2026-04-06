"""AI orchestration service for category and product reasoning."""

from __future__ import annotations

import re

from app.core.logger import get_logger
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


BUSY_MESSAGE = "All AI services are currently unavailable. Please try again later."


def _redact_sensitive(text: str) -> str:
    """Redact key-like query parameters and token fragments from log strings."""
    redacted = re.sub(r"((?:api_)?key=)[^&\s]+", r"\1[REDACTED]", text, flags=re.IGNORECASE)
    redacted = re.sub(r"\bsk-[A-Za-z0-9_-]+\b", "sk-[REDACTED]", redacted)
    return redacted


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
    providers: list[BaseCategoryProvider] = [GroqProvider(), OpenAIProvider(), GeminiProvider(), OllamaProvider()]
    provider_context = _normalize_context(context)

    errors: list[str] = []
    for provider in providers:
        last_error: str | None = None
        for attempt in range(1, 3):
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
                last_error = _redact_sensitive(str(exc))
                logger.warning(
                    "Provider failed provider=%s attempt=%d/2 error=%s",
                    provider.provider_name,
                    attempt,
                    last_error,
                )
                continue

        if last_error is not None:
            errors.append(f"{provider.provider_name}: {last_error}")

    joined_errors = " | ".join(errors)
    logger.error("All providers failed for category reasoning. errors=%s", joined_errors)
    raise RecommendationServiceError(BUSY_MESSAGE)
