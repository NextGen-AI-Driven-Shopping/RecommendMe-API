"""GROQ provider integration using OpenAI-compatible chat completions API."""

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


class GroqProvider(BaseCategoryProvider):
    """Category reasoning provider backed by GROQ."""

    provider_name = "groq"

    async def generate(
        self,
        *,
        query: str,
        context: list[dict[str, str]] | None = None,
        timeout_seconds: float = 20.0,
    ) -> CategoryReasoningResult:
        settings = get_settings()
        if not settings.GROQ_API_KEY:
            raise ProviderUnavailableError("GROQ_API_KEY is not configured")

        body = {
            "model": settings.GROQ_MODEL,
            "temperature": 0.2,
            "messages": build_category_reasoning_messages(query=query, context=context),
        }

        headers = {
            "Authorization": f"Bearer {settings.GROQ_API_KEY}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers=headers,
                    json=body,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"GROQ request failed: {exc}") from exc

        data = response.json()
        try:
            text = data["choices"][0]["message"]["content"]
            payload = extract_json_payload(text)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderResponseError(f"GROQ returned invalid output: {exc}") from exc

        return parse_provider_payload(payload)
