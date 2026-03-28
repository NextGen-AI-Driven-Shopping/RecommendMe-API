"""OpenAI provider integration."""

from __future__ import annotations

from openai import AsyncOpenAI

from app.config.settings import get_settings
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


class OpenAIProvider(BaseCategoryProvider):
    """Category reasoning provider backed by OpenAI."""

    provider_name = "openai"

    async def generate(
        self,
        *,
        query: str,
        context: list[dict[str, str]] | None = None,
        timeout_seconds: float = 8.0,
    ) -> CategoryReasoningResult:
        settings = get_settings()
        if not settings.OPENAI_API_KEY:
            raise ProviderUnavailableError("OPENAI_API_KEY is not configured")

        try:
            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, timeout=timeout_seconds)
            completion = await client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                temperature=0.2,
                messages=build_category_reasoning_messages(query=query, context=context),
            )
        except Exception as exc:
            raise ProviderUnavailableError(f"OpenAI request failed: {exc}") from exc

        try:
            text = completion.choices[0].message.content or ""
            payload = extract_json_payload(text)
        except (AttributeError, IndexError, TypeError, ValueError) as exc:
            raise ProviderResponseError(f"OpenAI returned invalid output: {exc}") from exc

        return parse_provider_payload(payload)
