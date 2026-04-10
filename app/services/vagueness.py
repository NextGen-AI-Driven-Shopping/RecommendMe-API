"""
Vagueness detection service — Tier 1 AI check.

Determines whether a user query contains sufficient context to generate
product recommendations, or whether a clarifying follow-up is needed.

Provider priority
-----------------
1. Groq     — primary tier, up to 4 models
2. OpenAI   — fallback tier, up to 4 models
3. Gemini   — fallback tier, available models
4. Dynamic  — DynamicIntentAnalyzer, no AI, no hardcoded strings

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

from app.config.settings import get_settings
from app.prompts.category_reasoning import extract_json_payload
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
    "groq":   8.0,
    "openai": 8.0,
    "gemini": 8.0,
    "ollama": 8.0,
}

BUSY_MESSAGE = "All AI services are currently unavailable. Please try again later."
INITIAL_FOLLOW_UP_LIMIT = 3


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
        return BUSY_MESSAGE


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

    # Keep up to 3 questions so the first clarification round is complete.
    cleaned = [str(q).strip() for q in (questions or []) if str(q).strip()][:INITIAL_FOLLOW_UP_LIMIT]
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
    if "{" in cleaned and "}" in cleaned:
        try:
            data: dict = extract_json_payload(cleaned)
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
                    # Preserve multiple AI follow-ups; UI can ask them sequentially.
                    follow_ups = [str(q).strip() for q in raw_qs if str(q).strip()][:INITIAL_FOLLOW_UP_LIMIT]
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
    configured_models = getattr(settings, "GROQ_MODELS", []) or []
    for m in [*configured_models, getattr(settings, "GROQ_MODEL", ""), "gpt-oss-120b", "kimi-k2-instruct", "qwen/qwen3-32b", "llama-3.3-70b-versatile"]:
        if m and m not in candidate_models:
            candidate_models.append(m)

    candidate_models = candidate_models[:4]

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
    """Fallback #2 — OpenAI with model retries."""
    try:
        import openai
    except ImportError as exc:
        raise VaguenessServiceError("openai package is not installed") from exc

    api_key = getattr(settings, "OPENAI_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise VaguenessServiceError("OPENAI_API_KEY is not configured; skipping OpenAI provider")

    candidate_models: list[str] = []
    configured_models = getattr(settings, "OPENAI_MODELS", []) or []
    for model in [*configured_models, getattr(settings, "OPENAI_MODEL", ""), "gpt-4.1", "gpt-4o", "gpt-4.1-mini"]:
        if model and model not in candidate_models:
            candidate_models.append(model)

    candidate_models = candidate_models[:4]
    last_exc: Exception | None = None

    for model in candidate_models:
        try:
            client = openai.AsyncOpenAI(api_key=api_key)
            completion = await client.chat.completions.create(
                model=model,
                messages=messages,  # type: ignore[arg-type]
                temperature=0,
                timeout=_PROVIDER_TIMEOUT["openai"],
            )
            text = (completion.choices[0].message.content or "").strip()
            return _parse_ai_response(text, query, "OpenAI")
        except Exception as exc:
            last_exc = exc
            logger.debug("[OpenAI] model=%s error=%s", model, exc)

    logger.warning("[OpenAI] all candidate models failed: %s", str(last_exc)[:120])
    raise VaguenessServiceError(f"OpenAI API failed: {str(last_exc)[:50]}") from last_exc


async def _classify_with_gemini(
    query: str, messages: Messages, settings
) -> VaguenessResult:
    """Fallback #3 — Google Gemini with model retries."""
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

    candidate_models: list[str] = []
    configured_models = getattr(settings, "GEMINI_MODELS", []) or []
    for model in [*configured_models, getattr(settings, "GEMINI_MODEL", ""), "gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash"]:
        if model and model not in candidate_models:
            candidate_models.append(model)

    candidate_models = candidate_models[:4]
    last_exc: Exception | None = None

    for model in candidate_models:
        try:
            async with httpx.AsyncClient(timeout=_PROVIDER_TIMEOUT["gemini"]) as client:
                response = await client.post(
                    "https://generativelanguage.googleapis.com/v1beta/models/"
                    f"{model}:generateContent?key={api_key}",
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
        except Exception as exc:
            last_exc = exc
            logger.debug("[Gemini] model=%s error=%s", model, exc)

    logger.warning("[Gemini] all candidate models failed: %s", str(last_exc)[:120])
    raise VaguenessServiceError(f"Gemini API failed: {str(last_exc)[:50]}") from last_exc


async def _classify_with_ollama(
    query: str, messages: Messages, settings
) -> VaguenessResult:
    """Final fallback — local Ollama with OpenAI-like chat framing."""
    ollama_url = (getattr(settings, "OLLAMA_URL", "") or "http://localhost:11434").strip()
    candidate_models: list[str] = []
    configured_models = getattr(settings, "OLLAMA_MODELS", []) or []
    for model in [*configured_models, getattr(settings, "OLLAMA_MODEL", ""), "phi3", "phi3:latest", "llama3.2"]:
        if model and model not in candidate_models:
            candidate_models.append(model)

    last_exc: Exception | None = None
    for model_name in candidate_models[:4]:
        payload = {
            "model": model_name,
            "stream": False,
            "messages": messages,
        }

        try:
            async with httpx.AsyncClient(timeout=_PROVIDER_TIMEOUT["ollama"]) as client:
                response = await client.post(f"{ollama_url.rstrip('/')}/api/chat", json=payload)
                if response.status_code == 404:
                    prompt = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages)
                    response = await client.post(
                        f"{ollama_url.rstrip('/')}/api/generate",
                        json={
                            "model": model_name,
                            "prompt": prompt,
                            "stream": False,
                        },
                    )
                response.raise_for_status()
            payload_json = response.json()
            text = ((payload_json.get("message", {}) or {}).get("content") or payload_json.get("response") or "").strip()
            try:
                return _parse_ai_response(text, query, "Ollama")
            except VaguenessServiceError:
                # Some local models return free-form text. Fall back to deterministic
                # local classification instead of failing the entire request.
                fallback_result = _dynamic_classification(query)
                fallback_result.provider = "Ollama+Dynamic"
                return fallback_result
        except Exception as exc:
            last_exc = exc
            logger.debug("[Ollama] model=%s error=%s", model_name, exc)

    raise VaguenessServiceError(f"Ollama API failed: {str(last_exc)[:80]}") from last_exc


async def _with_retries(name: str, provider_fn, query: str, messages: Messages, settings, attempts: int = 2) -> VaguenessResult:
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await provider_fn(query, messages, settings)
        except Exception as exc:
            last_exc = exc
            logger.warning("[%s] attempt %d/%d failed: %s", name, attempt, attempts, str(exc)[:140])
    raise VaguenessServiceError(f"{name} failed after {attempts} attempts: {last_exc}")


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
    ("Groq",    _classify_with_groq),
    ("OpenAI",  _classify_with_openai),
    ("Gemini",  _classify_with_gemini),
    ("Ollama",  _classify_with_ollama),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def classify_vagueness(
    query: str,
    *,
    allow_fallback: bool = True,
    domain_hint: str | None = None,
) -> VaguenessResult:
    """
    Classify whether a user query is CLEAR, VAGUE, or needs a RETRY.

    Provider chain: Groq → OpenAI → Gemini → Dynamic analyser.

    When the result is ``Classification.RETRY`` (all providers failed and the
    dynamic analyser also produced nothing), the caller should surface
    :attr:`VaguenessResult.retry_message` to the user, asking them to
    rephrase with more detail.

    Args:
        query:          User search query string (non-empty).
        allow_fallback: Try next provider on failure when ``True``.
                        Raises :class:`VaguenessServiceError` immediately
                        on first failure when ``False``.
        domain_hint:    Optional domain pre-detected by intent_engine.
                        Passed to the prompt so the AI adapts questions.

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
    messages = build_vagueness_prompt(query, domain_hint=domain_hint)

    # ── AI providers ──────────────────────────────────────────────────────
    for name, provider_fn in _AI_PROVIDERS:
        try:
            result = await _with_retries(name, provider_fn, query, messages, settings, attempts=2)
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

    logger.warning("All AI providers failed for vagueness classification.")
    return VaguenessResult(classification=Classification.RETRY, provider="busy")