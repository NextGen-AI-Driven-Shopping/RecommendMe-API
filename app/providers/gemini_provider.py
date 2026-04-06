"""Google Gemini provider integration."""

from __future__ import annotations

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


class GeminiProvider(BaseCategoryProvider):
    """Category reasoning provider backed by Gemini."""

    provider_name = "gemini"

    async def generate(
        self,
        *,
        query: str,
        context: list[dict[str, str]] | None = None,
        timeout_seconds: float = 8.0,
    ) -> CategoryReasoningResult:
        settings = get_settings()
        if not settings.GEMINI_API_KEY:
            raise ProviderUnavailableError("GEMINI_API_KEY is not configured")

        messages = build_category_reasoning_messages(query=query, context=context)
        prompt_text = "\n".join(message["content"] for message in messages)

        body = {
            "contents": [{"parts": [{"text": prompt_text}]}],
            "generationConfig": {"temperature": 0.2},
        }
        params = {"key": settings.GEMINI_API_KEY}

        # Try configured models first, then quality defaults.
        candidate_models: list[tuple[str, str]] = []
        preferred = [
            *(settings.GEMINI_MODELS or []),
            settings.GEMINI_MODEL,
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-2.0-flash",
        ]
        deduped: list[str] = []
        for model in preferred:
            if model and model not in deduped:
                deduped.append(model)
        for m in deduped[:4]:
            for api_ver in ["v1", "v1beta"]:
                entry = (m, api_ver)
                if entry not in candidate_models:
                    candidate_models.append(entry)

        last_error: str | None = None
        for model_name, api_version in candidate_models:
            url = f"https://generativelanguage.googleapis.com/{api_version}/models/{model_name}:generateContent"
            try:
                async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                    response = await client.post(url, params=params, json=body)

                if response.status_code in (400, 404) and (model_name, api_version) != candidate_models[-1]:
                    last_error = f"model={model_name} api={api_version} status={response.status_code}"
                    continue

                response.raise_for_status()
            except httpx.HTTPError as exc:
                if (model_name, api_version) != candidate_models[-1]:
                    last_error = f"model={model_name} api={api_version} {exc}"
                    continue
                raise ProviderUnavailableError(f"Gemini request failed: {exc}") from exc

            data = response.json()
            try:
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                payload = extract_json_payload(text)
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                raise ProviderResponseError(f"Gemini returned invalid output: {exc}") from exc

            return parse_provider_payload(payload)

        raise ProviderUnavailableError(
            f"Gemini request failed for all candidate models. Last error: {last_error or 'unknown'}"
        )
