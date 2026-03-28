from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.core.config import get_settings
from app.prompts.category_reasoning import extract_json_payload
from app.providers import GeminiProvider, GroqProvider, OllamaProvider, OpenAIProvider
from app.providers.base import (
    CategoryReasoningResult,
    ProviderError,
    ProviderResponseError,
    ProviderUnavailableError,
    RecommendedProductInfo,
    parse_provider_payload,
)

logger = logging.getLogger(__name__)


class RecommendationServiceError(Exception):
    """Raised when category recommendation reasoning fails across providers."""


_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Trekking Backpack": ("backpack", "rucksack", "bag"),
    "Trekking Shoes": ("shoes", "boots", "footwear"),
    "Tent": ("tent", "shelter"),
    "Headphones": ("headphones", "earbuds", "headset"),
    "Laptop": ("laptop", "notebook"),
    "Phone": ("phone", "smartphone", "mobile"),
    "Kitchen Essentials": ("kitchen", "cookware", "utensils", "pan", "pot"),
    "Apartment Essentials": ("apartment", "home essentials", "room setup"),
    "Gift Picks": ("gift", "present"),
}

_FEATURE_KEYWORDS = (
    "waterproof",
    "lightweight",
    "durable",
    "portable",
    "compact",
    "wireless",
    "noise cancelling",
    "bass",
    "gaming",
    "student",
    "budget",
    "premium",
    "professional",
)


def _split_query_and_preferences(query: str) -> tuple[str, str]:
    marker = "User preferences:"
    if marker not in query:
      cleaned = " ".join(query.split()).strip()
      return cleaned, ""

    base_query, preference_text = query.split(marker, 1)
    return " ".join(base_query.split()).strip(" ."), " ".join(preference_text.split()).strip()


def _extract_budget_hint(query: str) -> str | None:
    match = re.search(r"((?:under|below|around|between)\s+[^\.,;\n]+)", query, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    currency_match = re.search(r"([₹$€£]\s?\d[\d,]*(?:\s?-\s?[₹$€£]?\d[\d,]*)?)", query)
    if currency_match:
        return currency_match.group(1).strip()

    return None


def _extract_features(query: str) -> list[str]:
    lowered = query.lower()
    return [feature for feature in _FEATURE_KEYWORDS if feature in lowered]


def _infer_categories(query: str) -> list[str]:
    lowered = query.lower()
    matches = [
        category
        for category, keywords in _CATEGORY_KEYWORDS.items()
        if any(keyword in lowered for keyword in keywords)
    ]

    if matches:
        return matches[:3]

    if any(term in lowered for term in ("trek", "hiking", "camp")):
        return ["Trekking Gear"]
    if "student" in lowered:
        return ["Student Essentials"]
    if "gift" in lowered:
        return ["Gift Picks"]

    cleaned = " ".join(query.split())[:60].strip()
    return [cleaned.title() if cleaned else "Recommended Picks"]


def _build_dynamic_products(category: str, query: str) -> list[RecommendedProductInfo]:
    base_query, preference_text = _split_query_and_preferences(query)
    query_context = f"{base_query} {preference_text}".strip()
    budget_hint = _extract_budget_hint(query_context)
    features = _extract_features(query_context)
    feature_suffix = f" with {' and '.join(features[:2])}" if features else ""
    budget_suffix = f" {budget_hint}" if budget_hint else ""

    return [
        RecommendedProductInfo(
            name=f"Best overall {category.lower()}{feature_suffix}{budget_suffix}".strip(),
            explanation="Balanced performance, reliability, and value for the stated needs.",
            label="Best Overall",
        ),
        RecommendedProductInfo(
            name=f"Value-focused {category.lower()}{budget_suffix}".strip(),
            explanation="A practical pick that keeps cost and usability in balance.",
            label="Value Pick",
        ),
        RecommendedProductInfo(
            name=f"Feature-first {category.lower()}{feature_suffix}".strip(),
            explanation="Prioritizes the most important features mentioned in the request.",
            label="Feature Match",
        ),
    ]


def _normalize_context(context: list[Any] | None) -> list[dict[str, str]]:
    """Normalize conversation history into provider-safe role/content dicts."""
    if not context:
        return []

    normalized: list[dict[str, str]] = []
    for item in context:
        role = getattr(item, "role", None) if not isinstance(item, dict) else item.get("role")
        content = getattr(item, "content", None) if not isinstance(item, dict) else item.get("content")

        role_value = str(role).strip().lower() if role is not None else ""
        content_value = str(content).strip() if content is not None else ""

        if role_value in {"user", "assistant"} and content_value:
            normalized.append({"role": role_value, "content": content_value})

    return normalized


def _coerce_to_result(payload: Any) -> CategoryReasoningResult:
    """Convert provider payloads into validated CategoryReasoningResult."""
    if isinstance(payload, CategoryReasoningResult):
        return payload
    if isinstance(payload, dict):
        return parse_provider_payload(payload)
    if isinstance(payload, str):
        return parse_provider_payload(extract_json_payload(payload))
    raise ProviderResponseError(f"Unsupported provider payload type: {type(payload)!r}")


def _is_valid_ollama_url(url: str) -> bool:
    cleaned = (url or "").strip().lower()
    return cleaned.startswith("http://") or cleaned.startswith("https://")


def _build_local_fallback(query: str) -> CategoryReasoningResult:
    """Create a deterministic, non-AI fallback plan when providers are unavailable."""
    subject, preference_text = _split_query_and_preferences(query or "your request")
    subject = subject[:80] if subject else "your request"
    categories = _infer_categories(subject)
    primary_category = categories[0]
    analysis_text = f"{subject} {preference_text}".strip()
    budget_hint = _extract_budget_hint(analysis_text)
    features = _extract_features(analysis_text)

    detail_parts: list[str] = []
    if budget_hint:
        detail_parts.append(f"budget hint: {budget_hint}")
    if features:
        detail_parts.append(f"feature focus: {', '.join(features[:3])}")

    dynamic_reasoning = (
        f"Live AI reasoning is temporarily unavailable, so here are practical starter picks for {primary_category.lower()} "
        f"based on '{subject}'."
    )
    if detail_parts:
        dynamic_reasoning += f" I also used your {', '.join(detail_parts)}."
    elif preference_text:
        dynamic_reasoning += " I also used the preferences you shared in the chat."

    return CategoryReasoningResult(
        categories=categories,
        reasoning=dynamic_reasoning,
        recommended_products=_build_dynamic_products(primary_category, analysis_text),
    )


async def generate_category_plan(
    query: str,
    context: list[Any] | None = None,
) -> CategoryReasoningResult:
    """Generate category reasoning with deterministic provider fallback."""
    normalized_context = _normalize_context(context)
    settings = get_settings()

    providers = []
    if settings.GEMINI_API_KEY:
        providers.append(GeminiProvider())
    if settings.GROQ_API_KEY:
        providers.append(GroqProvider())
    if settings.OPENAI_API_KEY:
        providers.append(OpenAIProvider())
    if _is_valid_ollama_url(settings.OLLAMA_URL):
        providers.append(OllamaProvider())

    provider_errors: list[str] = []
    if not providers:
        logger.warning("No AI providers are configured. Using local fallback category plan.")
        return _build_local_fallback(query)

    for provider in providers:
        try:
            payload = await provider.generate(query=query, context=normalized_context)
            return _coerce_to_result(payload)
        except (ProviderUnavailableError, ProviderResponseError, ProviderError, json.JSONDecodeError, ValueError) as exc:
            provider_name = getattr(provider, "provider_name", provider.__class__.__name__)
            error_msg = f"{provider_name}: {exc}"
            provider_errors.append(error_msg)
            logger.warning("Category reasoning provider failed %s", error_msg)
            continue

    logger.error("All configured providers failed. Falling back to local category plan.")
    return _build_local_fallback(query)
