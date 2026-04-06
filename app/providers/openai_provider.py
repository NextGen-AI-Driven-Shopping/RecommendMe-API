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

        candidate_models: list[str] = []
        for model in [
            *(settings.OPENAI_MODELS or []),
            settings.OPENAI_MODEL,
            "gpt-4.1",
            "gpt-4o",
            "gpt-4.1-mini",
        ]:
            if model and model not in candidate_models:
                candidate_models.append(model)

        candidate_models = candidate_models[:4]
        completion = None
        last_exc: Exception | None = None

        for model in candidate_models:
            try:
                client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, timeout=timeout_seconds)
                completion = await client.chat.completions.create(
                    model=model,
                    temperature=0.2,
                    messages=build_category_reasoning_messages(query=query, context=context),
                )
                break
            except Exception as exc:
                last_exc = exc
                if model == candidate_models[-1]:
                    raise ProviderUnavailableError(f"OpenAI request failed: {exc}") from exc
                continue

        if completion is None:
            raise ProviderUnavailableError(f"OpenAI request failed: {last_exc}")

        try:
            text = completion.choices[0].message.content or ""
            payload = extract_json_payload(text)
        except (AttributeError, IndexError, TypeError, ValueError) as exc:
            raise ProviderResponseError(f"OpenAI returned invalid output: {exc}") from exc

        return parse_provider_payload(payload)
