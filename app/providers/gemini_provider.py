"""Google Gemini provider integration."""

from __future__ import annotations

import httpx

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


class GeminiProvider(BaseCategoryProvider):
    """Category reasoning provider backed by Gemini."""

    provider_name = "gemini"

    async def generate(
        self,
        *,
        query: str,
        context: list[dict[str, str]] | None = None,
        timeout_seconds: float = 20.0,
    ) -> CategoryReasoningResult:
        settings = get_settings()
        if not settings.GEMINI_API_KEY:
            raise ProviderUnavailableError("GEMINI_API_KEY is not configured")

        messages = build_category_reasoning_messages(query=query, context=context)
        prompt_text = "\n".join(message["content"] for message in messages)

        model = settings.GEMINI_MODEL
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        )
        params = {"key": settings.GEMINI_API_KEY}

        body = {
            "contents": [{"parts": [{"text": prompt_text}]}],
            "generationConfig": {"temperature": 0.2},
        }

        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.post(url, params=params, json=body)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"Gemini request failed: {exc}") from exc

        data = response.json()
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            payload = extract_json_payload(text)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderResponseError(f"Gemini returned invalid output: {exc}") from exc

        return parse_provider_payload(payload)
