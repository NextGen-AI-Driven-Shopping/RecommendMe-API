"""
Vagueness detection service — Tier 1 AI check.

Determines whether a user query contains sufficient context to generate
product recommendations, or whether a clarifying follow-up is needed.

Provider priority
-----------------
1. Ollama   — local model, primary (fast, free, private)
2. Groq     — cloud fallback (fast, free tier)
3. OpenAI   — cloud fallback #2 (GPT-4o-mini)
4. Gemini   — cloud fallback #3
5. Dynamic  — DynamicIntentAnalyzer, no AI, no hardcoded strings

If DynamicIntentAnalyzer produces no questions, the classification is set
to ``RETRY`` — the caller should prompt the user to re-enter their query
with more detail. No hardcoded question strings exist anywhere in this
module.

Return values
-------------
  classification = "CLEAR"  — query is specific enough for recommendations.
  classification = "VAGUE"  — query needs follow-up; ``follow_ups`` is set.
  classification = "RETRY"  — all providers failed; ask user to rephrase.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import TypeAlias

import httpx

from app.core.config import get_settings
from app.core.logger import get_logger
from app.prompts.vagueness_check import build_vagueness_prompt
from app.services.dynamic_intent_analyzer import (
    DynamicFollowUpGenerator,
    DynamicIntentAnalyzer,
)

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

Messages: TypeAlias = list[dict[str, str]]

_PROVIDER_TIMEOUT: dict[str, float] = {
    "ollama": 8.0,
    "groq":   10.0,
    "openai": 12.0,
    "gemini": 10.0,
}


class Classification(str, Enum):
    CLEAR = "CLEAR"
    VAGUE = "VAGUE"
    RETRY = "RETRY"   # all providers exhausted, ask user to rephrase


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


@dataclass
class VaguenessResult:
    """Encapsulates the output of the vagueness classification step."""

    classification: Classification
    follow_ups: list[str] | None = field(default=None)
    provider: str = field(default="unknown")

    # Convenience -----------------------------------------------------------------

    @property
    def is_clear(self) -> bool:
        return self.classification == Classification.CLEAR

    @property
    def is_vague(self) -> bool:
        return self.classification == Classification.VAGUE

    @property
    def needs_retry(self) -> bool:
        """
        True when all AI providers failed and the dynamic analyser produced
        nothing useful.  The caller should tell the user to re-enter their
        query with more detail.
        """
        return self.classification == Classification.RETRY

    @property
    def retry_message(self) -> str:
        """
        Human-facing message to display when ``needs_retry`` is True.

        The message is deliberately specific so the user knows *what* to add,
        not just that their query was "too vague".
        """
        return (
            "We couldn't figure out what you need from that. "
            "Try adding the activity, intended use, terrain, or a key feature — "
            "for example: \"trekking boots for rocky mountain trails\" "
            "or \"wireless headphones for daily commuting under ₹3000\"."
        )


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class VaguenessServiceError(Exception):
    """Raised when a single provider call fails."""


class AllProvidersFailedError(VaguenessServiceError):
    """Raised when every provider (including dynamic) produces nothing."""


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _strip_code_fences(text: str) -> str:
    """Remove markdown ``` fences that some models wrap JSON in."""
    return "\n".join(
        line for line in text.strip().splitlines()
        if not line.strip().startswith("```")
    ).strip()


def _dynamic_follow_ups(query: str) -> list[str]:
    """
    Generate follow-ups using DynamicIntentAnalyzer.

    Returns an empty list if the analyser produces nothing — callers must
    handle that case; this function does NOT supply any fallback strings.
    """
    analyzer  = DynamicIntentAnalyzer()
    signals   = analyzer.extract_domain_signals(query)
    missing   = analyzer.determine_missing_info(signals)
    generator = DynamicFollowUpGenerator()
    questions = generator.generate_from_signals(query, signals, missing)

    # Filter blanks, cap at 3
    cleaned = [str(q).strip() for q in (questions or []) if str(q).strip()][:3]
    logger.debug("[Dynamic] generated %d follow-ups for query=%r", len(cleaned), query[:60])
    return cleaned


def _parse_ai_response(raw: str, query: str, provider: str) -> VaguenessResult:
    """
    Parse a raw LLM string into a :class:`VaguenessResult`.

    Attempt order:
        1. JSON extraction
        2. Keyword scan of raw text
        3. Raise :class:`VaguenessServiceError`

    When the model says VAGUE but provides no follow-ups, dynamic generation
    is attempted.  If dynamic generation also yields nothing, raises
    :class:`VaguenessServiceError` so the caller falls through to the next
    provider — we never invent hardcoded question strings.
    """
    cleaned = _strip_code_fences(raw)

    # ── 1. JSON extraction ────────────────────────────────────────────────
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end > start:
        try:
            data: dict = json.loads(cleaned[start : end + 1])
            cls_raw = str(data.get("classification", "")).upper().strip()

            if cls_raw == Classification.CLEAR:
                logger.info("[%s] CLEAR (JSON)", provider)
                return VaguenessResult(
                    classification=Classification.CLEAR, provider=provider
                )

            if cls_raw == Classification.VAGUE:
                raw_qs = (
                    data.get("follow_ups")
                    or data.get("followups")
                    or data.get("questions")
                )
                if isinstance(raw_qs, list) and raw_qs:
                    follow_ups = [str(q).strip() for q in raw_qs if str(q).strip()][:3]
                    logger.info(
                        "[%s] VAGUE — %d AI follow-ups", provider, len(follow_ups)
                    )
                else:
                    logger.info(
                        "[%s] VAGUE — no follow-ups in JSON, trying dynamic", provider
                    )
                    follow_ups = _dynamic_follow_ups(query)
                    if not follow_ups:
                        raise VaguenessServiceError(
                            f"[{provider}] VAGUE but dynamic analyser produced nothing"
                        )

                return VaguenessResult(
                    classification=Classification.VAGUE,
                    follow_ups=follow_ups,
                    provider=provider,
                )

        except VaguenessServiceError:
            raise
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            logger.debug("[%s] JSON parse failed: %s", provider, exc)

    # ── 2. Keyword scan ───────────────────────────────────────────────────
    upper = cleaned.upper()
    if "CLEAR" in upper:
        logger.info("[%s] CLEAR (keyword scan)", provider)
        return VaguenessResult(
            classification=Classification.CLEAR, provider=provider
        )
    if "VAGUE" in upper:
        follow_ups = _dynamic_follow_ups(query)
        if not follow_ups:
            raise VaguenessServiceError(
                f"[{provider}] VAGUE keyword found but dynamic analyser produced nothing"
            )
        logger.info("[%s] VAGUE (keyword scan, dynamic follow-ups)", provider)
        return VaguenessResult(
            classification=Classification.VAGUE,
            follow_ups=follow_ups,
            provider=provider,
        )

    raise VaguenessServiceError(
        f"[{provider}] unparseable response: {raw[:200]!r}"
    )


# ---------------------------------------------------------------------------
# Provider classifiers
# ---------------------------------------------------------------------------


async def _classify_with_ollama(
    query: str, messages: Messages, settings
) -> VaguenessResult:
    """Primary classifier — local Ollama instance."""
    base_url = getattr(settings, "OLLAMA_URL", "").rstrip("/")
    model    = getattr(settings, "OLLAMA_MODEL", "")

    if not base_url:
        raise VaguenessServiceError("OLLAMA_URL is not configured; skipping Ollama provider")

    if not model:
        raise VaguenessServiceError("OLLAMA_MODEL is not configured; skipping Ollama provider")

    try:
        async with httpx.AsyncClient(timeout=_PROVIDER_TIMEOUT["ollama"]) as client:
            response = await client.post(
                f"{base_url}/api/chat",
                json={"model": model, "messages": messages, "stream": False},
            )
            response.raise_for_status()

        text = response.json()["message"]["content"].strip()
        return _parse_ai_response(text, query, "Ollama")
    except Exception as e:
        logger.warning("[Ollama] Connection failed (is Ollama running on %s?): %s", base_url, str(e)[:100])
        raise VaguenessServiceError(f"Ollama unavailable at {base_url}: {str(e)[:50]}") from e


async def _classify_with_groq(
    query: str, messages: Messages, settings
) -> VaguenessResult:
    """Fallback #1 — Groq cloud with automatic model retry."""
    api_key = getattr(settings, "GROQ_API_KEY", "")
    if not api_key:
        raise VaguenessServiceError("GROQ_API_KEY is not configured; skipping Groq provider")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    candidate_models: list[str] = []
    for m in [
        getattr(settings, "GROQ_MODEL", ""),
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
    ]:
        if m and m not in candidate_models:
            candidate_models.append(m)

    last_exc: Exception | None = None

    for model in candidate_models:
        try:
            async with httpx.AsyncClient(timeout=_PROVIDER_TIMEOUT["groq"]) as client:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers=headers,
                    json={"model": model, "temperature": 0, "messages": messages},
                )

            if response.status_code == 400 and model != candidate_models[-1]:
                logger.debug("[Groq] model=%s → 400, trying next", model)
                continue

            response.raise_for_status()
            text = (
                response.json()
                .get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            return _parse_ai_response(text, query, "Groq")

        except VaguenessServiceError:
            raise
        except Exception as exc:
            last_exc = exc
            logger.debug("[Groq] model=%s error: %s", model, exc)

    logger.warning("[Groq] All models failed (invalid API key? rate limited?: %s", str(last_exc)[:100])
    raise VaguenessServiceError(
        f"All Groq models failed. Last: {str(last_exc)[:50]}"
    ) from last_exc


async def _classify_with_openai(
    query: str, messages: Messages, settings
) -> VaguenessResult:
    """Fallback #2 — OpenAI GPT-4o-mini."""
    try:
        import openai
    except ImportError as exc:
        raise VaguenessServiceError("openai package is not installed") from exc

    api_key = getattr(settings, "OPENAI_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise VaguenessServiceError("OPENAI_API_KEY is not configured; skipping OpenAI provider")

    try:
        client     = openai.AsyncOpenAI(api_key=api_key)
        completion = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,  # type: ignore[arg-type]
            temperature=0,
            timeout=_PROVIDER_TIMEOUT["openai"],
        )
        text = (completion.choices[0].message.content or "").strip()
        return _parse_ai_response(text, query, "OpenAI")
    except Exception as e:
        logger.warning("[OpenAI] API call failed (invalid API key? rate limited? network error?): %s", str(e)[:100])
        raise VaguenessServiceError(f"OpenAI API failed: {str(e)[:50]}") from e


async def _classify_with_gemini(
    query: str, messages: Messages, settings
) -> VaguenessResult:
    """Fallback #3 — Google Gemini 1.5 Flash."""
    api_key = getattr(settings, "GEMINI_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise VaguenessServiceError("GEMINI_API_KEY is not configured; skipping Gemini provider")

    # Gemini v1beta REST has no system role; fold system turns into user turns
    gemini_messages = [
        {
            "role": "user" if m["role"] in ("user", "system") else "model",
            "parts": [{"text": m["content"]}],
        }
        for m in messages
    ]

    try:
        async with httpx.AsyncClient(timeout=_PROVIDER_TIMEOUT["gemini"]) as client:
            response = await client.post(
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"gemini-1.5-flash:generateContent?key={api_key}",
                json={"contents": gemini_messages},
            )
            response.raise_for_status()

        text = (
            response.json()
            .get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
            .strip()
        )
        return _parse_ai_response(text, query, "Gemini")
    except Exception as e:
        logger.warning("[Gemini] API call failed (invalid API key? quota exceeded? network error?): %s", str(e)[:100])
        raise VaguenessServiceError(f"Gemini API failed: {str(e)[:50]}") from e


def _dynamic_classification(query: str) -> VaguenessResult:
    """
    Fully offline fallback using DynamicIntentAnalyzer.

    Returns ``Classification.RETRY`` when the analyser cannot produce
    follow-up questions — the caller then surfaces ``retry_message`` to the
    user.  No hardcoded question strings are ever injected here.
    """
    analyzer = DynamicIntentAnalyzer()

    if analyzer.is_query_clear(query):
        logger.info("[Dynamic] CLEAR")
        return VaguenessResult(
            classification=Classification.CLEAR, provider="dynamic"
        )

    follow_ups = _dynamic_follow_ups(query)
    if follow_ups:
        logger.info("[Dynamic] VAGUE — %d follow-ups", len(follow_ups))
        return VaguenessResult(
            classification=Classification.VAGUE,
            follow_ups=follow_ups,
            provider="dynamic",
        )

    # Cannot generate meaningful questions — tell user to rephrase
    logger.warning(
        "[Dynamic] Could not generate follow-ups for query=%r; returning RETRY",
        query[:60],
    )
    return VaguenessResult(classification=Classification.RETRY, provider="dynamic")


# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------

_AI_PROVIDERS = [
    ("Ollama",  _classify_with_ollama),
    ("Groq",    _classify_with_groq),
    ("OpenAI",  _classify_with_openai),
    ("Gemini",  _classify_with_gemini),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def classify_vagueness(
    query: str,
    *,
    allow_fallback: bool = True,
) -> VaguenessResult:
    """
    Classify whether a user query is CLEAR, VAGUE, or needs a RETRY.

    Provider chain: Ollama → Groq → OpenAI → Gemini → Dynamic analyser.

    When the result is ``Classification.RETRY`` (all providers failed and the
    dynamic analyser also produced nothing), the caller should surface
    :attr:`VaguenessResult.retry_message` to the user, asking them to
    rephrase with more detail.

    Args:
        query:          User search query string (non-empty).
        allow_fallback: Try next provider on failure when ``True``.
                        Raises :class:`VaguenessServiceError` immediately
                        on first failure when ``False``.

    Returns:
        :class:`VaguenessResult`.

    Raises:
        ValueError:              If *query* is blank or whitespace-only.
        VaguenessServiceError:   If *allow_fallback* is ``False`` and the
                                 primary provider fails.
        AllProvidersFailedError: If every provider AND dynamic fails.
    """
    if not query or not query.strip():
        raise ValueError("query must be a non-empty string")

    query    = query.strip()
    settings = get_settings()
    messages = build_vagueness_prompt(query)

    # ── AI providers ──────────────────────────────────────────────────────
    for name, provider_fn in _AI_PROVIDERS:
        try:
            result = await provider_fn(query, messages, settings)
            logger.info("classify_vagueness success via %s", name)
            return result

        except VaguenessServiceError as exc:
            if not allow_fallback:
                raise
            logger.warning("[%s] failed (%s); trying next provider.", name, exc)

        except Exception as exc:
            if not allow_fallback:
                raise VaguenessServiceError(str(exc)) from exc
            logger.warning(
                "[%s] unexpected error (%s); trying next provider.", name, exc
            )

    # ── Dynamic analyser (no AI, no hardcoded strings) ────────────────────
    logger.warning("All AI providers failed; using dynamic classification.")
    try:
        return _dynamic_classification(query)
    except Exception as exc:
        raise AllProvidersFailedError(
            f"Every provider failed, including dynamic analyser: {exc}"
        ) from exc