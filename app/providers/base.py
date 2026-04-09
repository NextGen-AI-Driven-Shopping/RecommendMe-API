"""Base interfaces and shared validation for AI providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ValidationError, field_validator


class ProviderError(Exception):
    """Base exception raised by provider integrations."""


class ProviderUnavailableError(ProviderError):
    """Raised when a provider cannot be reached or is misconfigured."""


class ProviderResponseError(ProviderError):
    """Raised when provider output cannot be validated."""


class RecommendedProductInfo(BaseModel):
    """Detailed info for a recommended product."""
    name: str
    explanation: str
    label: str


class CategoryReasoningResult(BaseModel):
    """Normalized category reasoning result used by all providers."""

    categories: list[str]
    reasoning: str
    recommended_products: list[RecommendedProductInfo]
    # Optional domain/intent fields added by the new domain-agnostic prompt.
    # Providers that return them will populate these; legacy responses leave them None.
    domain: str | None = None
    intent: str | None = None

    @field_validator("categories")
    @classmethod
    def _validate_non_empty_list(cls, value: list[str]) -> list[str]:
        filtered = [item.strip() for item in value if item and item.strip()]
        if not filtered:
            raise ValueError("list must contain at least one non-empty value")
        return filtered

    @field_validator("recommended_products")
    @classmethod
    def _validate_non_empty_products(cls, value: list[RecommendedProductInfo]) -> list[RecommendedProductInfo]:
        if not value:
            raise ValueError("list must contain at least one recommended product")
        return value

    @field_validator("reasoning")
    @classmethod
    def _validate_reasoning(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("reasoning cannot be empty")
        return cleaned


class BaseCategoryProvider(ABC):
    """Interface for providers that can produce category reasoning outputs."""

    provider_name: str

    @abstractmethod
    async def generate(
        self,
        *,
        query: str,
        context: list[dict[str, str]] | None = None,
        timeout_seconds: float = 8.0,
        domain_hint: str | None = None,
    ) -> CategoryReasoningResult:
        """Generate categories, reasoning, and recommended items (domain-agnostic)."""


def parse_provider_payload(payload: Any) -> CategoryReasoningResult:
    """Validate and normalize provider output payloads."""
    if isinstance(payload, str):
        raise ProviderResponseError("Provider returned plain string instead of JSON payload")
    if not isinstance(payload, dict):
        raise ProviderResponseError(f"Provider returned unexpected payload type: {type(payload)!r}")

    try:
        return CategoryReasoningResult.model_validate(payload)
    except ValidationError as exc:
        raise ProviderResponseError(f"Provider payload validation failed: {exc}") from exc
