"""
Vagueness detection service — Tier 1 AI check.

Determines whether a user query contains sufficient context to generate
product recommendations, or whether a clarifying follow-up question is
needed first.

Classification strategy
-----------------------
1. Primary: Call the local Ollama model (fast, no cost, no network egress).
2. Fallback: Call GPT-4o-mini via the OpenAI API if Ollama is unavailable
   or returns an unexpected response.

Return values
-------------
  classification = "CLEAR"  — query is specific enough for recommendations.
  classification = "VAGUE"  — query requires a follow-up clarification.
"""

import os
from dataclasses import dataclass, field

import httpx

from app.core.config import get_settings
from app.core.logger import get_logger
from app.prompts.vagueness_check import build_vagueness_prompt

logger = get_logger(__name__)


# --------------------------------------------------------------------------- #
# Result model
# --------------------------------------------------------------------------- #

@dataclass
class VaguenessResult:
    """Encapsulates the output of the vagueness classification step."""

    classification: str                     # "CLEAR" or "VAGUE"
    follow_ups: list[str] | None = field(default=None)


# --------------------------------------------------------------------------- #
# Custom exception
# --------------------------------------------------------------------------- #

class VaguenessServiceError(Exception):
    """Raised when both the Ollama call and the OpenAI fallback fail."""


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

async def classify_vagueness(
    query: str,
    allow_fallback: bool = True,
) -> VaguenessResult:
    """
    Classify whether a user query is CLEAR or VAGUE.

    Args:
        query:           User search query string.
        allow_fallback:  When True, retry with OpenAI GPT-4o-mini if Ollama
                         fails or returns an unexpected response.

    Returns:
        VaguenessResult with classification set to "CLEAR" or "VAGUE".

    Raises:
        VaguenessServiceError: If both providers fail and allow_fallback is True,
                               or if Ollama fails and allow_fallback is False.
    """
    settings = get_settings()

    # Build the ``/api/chat`` URL from the configured base URL.
    # Settings.OLLAMA_URL may or may not contain a trailing slash.
    base_url = settings.OLLAMA_URL.rstrip("/")
    model = settings.OLLAMA_MODEL
    messages = build_vagueness_prompt(query)

    def _default_follow_ups() -> list[str]:
        topic = query[:80].strip()
        return [
            f"What exact type of {topic} are you looking for?",
            "What budget range should I target?",
            "Any must-have features, brand preferences, or constraints?",
        ]

    # ------------------------------------------------------------------ #
    # Primary: Ollama (local model)
    # ------------------------------------------------------------------ #
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{base_url}/api/chat",
                json={"model": model, "messages": messages, "stream": False},
            )
            response.raise_for_status()

        data = response.json()
        text: str = data["message"]["content"].strip().upper()

        if "CLEAR" in text:
            logger.info(f"Ollama classified query as CLEAR")
            return VaguenessResult(classification="CLEAR")

        if "VAGUE" in text:
            logger.info(f"Ollama classified query as VAGUE")
            return VaguenessResult(classification="VAGUE", follow_ups=_default_follow_ups())

        raise VaguenessServiceError(f"Unexpected Ollama response: {text!r}")

    except VaguenessServiceError:
        # Re-raise if not using fallback.
        if not allow_fallback:
            raise
        logger.warning("Ollama returned unexpected output; attempting OpenAI fallback.")

    except Exception as ollama_exc:
        if not allow_fallback:
            raise VaguenessServiceError(f"Ollama call failed: {ollama_exc}") from ollama_exc
        logger.warning(f"Ollama unavailable ({ollama_exc!r}); attempting OpenAI fallback.")

    # ------------------------------------------------------------------ #
    # Fallback: OpenAI GPT-4o-mini
    # ------------------------------------------------------------------ #
    try:
        import openai  # Lazy import — openai is optional during local dev without a key.

        api_key = settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            raise VaguenessServiceError(
                "OPENAI_API_KEY is not configured; cannot use OpenAI fallback."
            )

        # openai >= 1.0 uses the client-based API.
        client = openai.AsyncOpenAI(api_key=api_key)
        completion = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0,
        )

        text = completion.choices[0].message.content.strip().upper()

        if "CLEAR" in text:
            logger.info("OpenAI fallback classified query as CLEAR")
            return VaguenessResult(classification="CLEAR")

        if "VAGUE" in text:
            logger.info("OpenAI fallback classified query as VAGUE")
            return VaguenessResult(classification="VAGUE", follow_ups=_default_follow_ups())

        raise VaguenessServiceError(f"Unexpected OpenAI fallback response: {text!r}")

    except VaguenessServiceError:
        raise
    except Exception as openai_exc:
        raise VaguenessServiceError(
            f"OpenAI fallback also failed: {openai_exc}"
        ) from openai_exc