"""Groq provider integration."""

from __future__ import annotations

from groq import Groq

from app.core.config import get_settings
from app.prompts.category_reasoning import (
    build_category_reasoning_messages,
    extract_json_payload,
)
from app.providers.base import (
    BaseCategoryProvider,
    CategoryReasoningResult,
    ProviderResponseError,
    ProviderUnavailableError,
    parse_provider_payload,
)


class GroqProvider(BaseCategoryProvider):
    """Category reasoning provider backed by Groq."""

    provider_name = "groq"

    async def generate(
        self,
        *,
        query: str,
        context: list[dict[str, str]] | None = None,
        timeout_seconds: float = 8.0,
    ) -> CategoryReasoningResult:
        settings = get_settings()
        if not settings.GROQ_API_KEY:
            raise ProviderUnavailableError("GROQ_API_KEY is not configured")

        client = Groq(api_key=settings.GROQ_API_KEY, timeout=timeout_seconds)

        try:
            completion = client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=build_category_reasoning_messages(query=query, context=context),
                temperature=0.2,
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            raise ProviderUnavailableError(f"Groq request failed: {exc}") from exc

        try:
            text = completion.choices[0].message.content or ""
            payload = extract_json_payload(text)
        except (AttributeError, IndexError, TypeError, ValueError) as exc:
            raise ProviderResponseError(f"Groq returned invalid output: {exc}") from exc

        return parse_provider_payload(payload)
