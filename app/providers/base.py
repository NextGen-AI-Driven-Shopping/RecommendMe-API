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


class ProductTypeInfo(BaseModel):
    """One product type entry with a unique context-aware description.

    Flow.md hierarchy:
        Category  (display label — exactly 1 per session)
          └── Product Type  (functional class — drives SERP query, max 10)
                └── Product Items  (real listings from SERP)
    """

    product_type: str
    """Functional class name used directly as the SERP search query."""

    description: str
    """Unique 2–3 sentence description referencing the user's specific context.

    Rules (from Flow.md §58-80):
    - Every description must be different — no repeated phrasing across types.
    - Must reference the user's actual context (terrain, mood, use case, etc.).
    - Length: 2–3 sentences maximum.
    - Tone: helpful and conversational. No promotional language.
    - Phrases like "a great option" or "highly recommended" are prohibited.
    """

    @field_validator("product_type")
    @classmethod
    def _validate_product_type(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("product_type cannot be empty")
        return cleaned

    @field_validator("description")
    @classmethod
    def _validate_description(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("description cannot be empty")
        return cleaned


class CategoryReasoningResult(BaseModel):
    """Normalized category reasoning result used by all providers.

    Flow.md mandates exactly ONE category per session, with up to 10 product types.
    Each product type has a unique description AND drives exactly one SERP call.
    """

    category: str
    """Display-only label for the session (e.g. 'Trekking Gear', 'Home Office Setup').
    Exactly 1 per session. Has no functional role in AI reasoning or SERP queries."""

    product_types: list[ProductTypeInfo]
    """Up to 10 product types, each with a unique description. These are the SERP query basis."""

    reasoning: str
    """Overall reasoning / summary shown to the user above the product list."""

    domain: str | None = None
    intent: str | None = None

    # ── Legacy compatibility shim ─────────────────────────────────────────────
    # Kept so that any code that still reads .categories or .recommended_products
    # won't crash. They derive from the canonical fields above.

    @property
    def categories(self) -> list[str]:
        """Legacy: returns [category] — the single category as a list."""
        return [self.category]

    @property
    def recommended_products(self) -> list[ProductTypeInfo]:
        """Legacy: alias for product_types."""
        return self.product_types

    @field_validator("category")
    @classmethod
    def _validate_category(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("category cannot be empty")
        return cleaned

    @field_validator("product_types")
    @classmethod
    def _validate_product_types(cls, value: list[ProductTypeInfo]) -> list[ProductTypeInfo]:
        if not value:
            raise ValueError("product_types must contain at least one entry")
        return value[:10]  # Enforce Flow.md max of 10

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
        """Generate 1 category + up to 10 product types with unique descriptions (domain-agnostic)."""


def parse_provider_payload(payload: Any) -> CategoryReasoningResult:
    """Validate and normalize provider output payloads."""
    if isinstance(payload, str):
        raise ProviderResponseError("Provider returned plain string instead of JSON payload")
    if not isinstance(payload, dict):
        raise ProviderResponseError(f"Provider returned unexpected payload type: {type(payload)!r}")

    # ── Handle legacy multi-category format gracefully ────────────────────────
    # Old providers return: {"categories": ["Cat1", "Cat2"], "recommended_products": [...], "reasoning": "..."}
    # New providers return: {"category": "Cat", "product_types": [...], "reasoning": "..."}
    if "categories" in payload and "category" not in payload:
        cats = payload.get("categories") or []
        payload = dict(payload)
        payload["category"] = cats[0] if cats else "Recommended Products"

    if "recommended_products" in payload and "product_types" not in payload:
        old_products = payload.get("recommended_products") or []
        payload = dict(payload)
        payload["product_types"] = [
            {
                "product_type": p.get("name", "") if isinstance(p, dict) else str(p),
                "description": p.get("explanation", "") if isinstance(p, dict) else "",
            }
            for p in old_products
            if (p.get("name") if isinstance(p, dict) else str(p))
        ]

    try:
        return CategoryReasoningResult.model_validate(payload)
    except ValidationError as exc:
        raise ProviderResponseError(f"Provider payload validation failed: {exc}") from exc
