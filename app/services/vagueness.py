"""
Vagueness detection service.

Tier 1 AI check: determines whether a user query contains sufficient
context to generate product recommendations without further clarification.

Strategy:
  1. Attempt classification using the local Ollama model (fast, free).
  2. Fall back to GPT-4o-mini if Ollama is unavailable or times out.

Returns:
  "CLEAR"  — query has enough context for recommendations.
  "VAGUE"  — query needs a follow-up clarification question.
"""

import os
import httpx
from dataclasses import dataclass

from app.prompts.vagueness_check import build_vagueness_prompt
from app.core.config import get_settings


@dataclass
class VaguenessResult:
    classification: str
    follow_ups: list[str] | None = None


class VaguenessServiceError(Exception):
    pass


async def classify_vagueness(query: str, allow_fallback: bool = True) -> VaguenessResult:
    """
    Classify whether a query is CLEAR or VAGUE.

    Args:
        query: user search query
        allow_fallback: enable OpenAI fallback if Ollama fails

    Returns:
        VaguenessResult
    """

    settings = get_settings()

    base_url = settings.ollama_base_url.rstrip("/")
    model = settings.ollama_model

    messages = build_vagueness_prompt(query)

    try:

        async with httpx.AsyncClient(timeout=10.0) as client:

            response = await client.post(
                f"{base_url}/api/chat",
                json={
                    "model": model,
                    "messages": messages,
                    "stream": False
                }
            )

            response.raise_for_status()

            data = response.json()

            text = data["message"]["content"].strip().upper()

            if "CLEAR" in text:
                return VaguenessResult(classification="CLEAR")

            if "VAGUE" in text:
                return VaguenessResult(classification="VAGUE")

            raise VaguenessServiceError(
                f"Unexpected model response: {text}"
            )

    except Exception as exc:

        if not allow_fallback:
            raise

        # OpenAI fallback
        try:
            import openai

            openai.api_key = os.getenv("OPENAI_API_KEY")

            response = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=messages,
            )

            text = response["choices"][0]["message"]["content"].strip().upper()

            if "CLEAR" in text:
                return VaguenessResult(classification="CLEAR")

            if "VAGUE" in text:
                return VaguenessResult(classification="VAGUE")

            raise VaguenessServiceError(
                f"Unexpected fallback response: {text}"
            )

        except Exception as fallback_exc:
            raise VaguenessServiceError(
                f"Ollama failed: {exc} | Fallback failed: {fallback_exc}"
            )