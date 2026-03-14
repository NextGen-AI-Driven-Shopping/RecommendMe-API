"""Ollama provider integration used as final category reasoning fallback."""

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


class OllamaProvider(BaseCategoryProvider):
    """Category reasoning provider backed by local Ollama."""

    provider_name = "ollama"

    async def generate(
        self,
        *,
        query: str,
        context: list[dict[str, str]] | None = None,
        timeout_seconds: float = 20.0,
    ) -> CategoryReasoningResult:
        settings = get_settings()

        body = {
            "model": settings.OLLAMA_MODEL,
            "stream": False,
            "messages": build_category_reasoning_messages(query=query, context=context),
        }

        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.post(
                    f"{settings.OLLAMA_URL.rstrip('/')}/api/chat",
                    json=body,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"Ollama request failed: {exc}") from exc

        data = response.json()
        try:
            text = data["message"]["content"]
            payload = extract_json_payload(text)
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderResponseError(f"Ollama returned invalid output: {exc}") from exc

        return parse_provider_payload(payload)
