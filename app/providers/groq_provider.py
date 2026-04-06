"""GROQ provider integration using OpenAI-compatible chat completions API."""

from __future__ import annotations

import json

import httpx

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


class GroqProvider(BaseCategoryProvider):
    """Category reasoning provider backed by GROQ."""

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

        messages = build_category_reasoning_messages(query=query, context=context)

        headers = {
            "Authorization": f"Bearer {settings.GROQ_API_KEY}",
            "Content-Type": "application/json",
        }

        candidate_models = [
            *(settings.GROQ_MODELS or []),
            settings.GROQ_MODEL,
            "gpt-oss-120b",
            "kimi-k2-instruct",
            "qwen/qwen3-32b",
            "llama-3.3-70b-versatile",
        ]
        deduped_models: list[str] = []
        for model in candidate_models:
            if model and model not in deduped_models:
                deduped_models.append(model)

        deduped_models = deduped_models[:4]

        last_error: str | None = None
        for model_name in deduped_models:
            body = {
                "model": model_name,
                "temperature": 0.2,
                "messages": messages,
            }

            try:
                async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                    response = await client.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers=headers,
                        json=body,
                    )

                if response.status_code == 400 and model_name != deduped_models[-1]:
                    detail = _extract_error_message(response)
                    last_error = f"model={model_name} {detail}".strip()
                    continue

                response.raise_for_status()
            except httpx.HTTPError as exc:
                if model_name != deduped_models[-1]:
                    last_error = f"model={model_name} {exc}"
                    continue
                suffix = f"; previous_error={last_error}" if last_error else ""
                raise ProviderUnavailableError(f"GROQ request failed: {exc}{suffix}") from exc

            data = response.json()
            try:
                text = data["choices"][0]["message"]["content"]
                payload = extract_json_payload(text)
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                raise ProviderResponseError(f"GROQ returned invalid output: {exc}") from exc

            return parse_provider_payload(payload)

        raise ProviderUnavailableError(
            f"GROQ request failed for all candidate models. Last error: {last_error or 'unknown'}"
        )


def _extract_error_message(response: httpx.Response) -> str:
    """Extract a concise provider error message from a Groq HTTP response."""
    try:
        payload = response.json()
    except json.JSONDecodeError:
        return response.text.strip()

    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str):
                return message
    return response.text.strip()
