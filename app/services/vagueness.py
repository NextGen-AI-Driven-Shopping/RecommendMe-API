from __future__ import annotations
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any
import httpx

from app.core.config import get_settings
from app.prompts.vagueness_check import build_vagueness_prompt

logger = logging.getLogger(__name__)

class VaguenessServiceError(Exception):
    """Raised when a single provider call fails."""

@dataclass
class VaguenessResult:
    classification: str
    follow_ups: list[str] | None = field(default=None)
    provider: str = field(default="unknown")

def safe_get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


_ACTIVITY_TERMS = {
    "trekking",
    "hiking",
    "camping",
    "travel",
    "trip",
    "vacation",
    "holiday",
    "beach",
    "tour",
    "touring",
    "resort",
    "bali",
    "gaming",
    "running",
    "office",
    "college",
    "study",
    "studying",
    "gym",
    "workout",
    "cooking",
    "photography",
}

_PRODUCT_TERMS = {
    "backpack",
    "bag",
    "shoes",
    "shoe",
    "boots",
    "jacket",
    "tent",
    "watch",
    "bottle",
    "laptop",
    "phone",
    "headphones",
    "earbuds",
    "camera",
    "stove",
    "mat",
    "socks",
    "gloves",
    "trekking-pole",
    "pole",
}

_FEATURE_HINTS = {
    "waterproof",
    "lightweight",
    "durable",
    "portable",
    "compact",
    "premium",
    "budget",
    "cheap",
    "best",
    "professional",
    "beginner",
    "advanced",
    "wireless",
    "bluetooth",
    "comfortable",
    "small",
    "large",
}

_TRAVEL_INTENT_PHRASES = (
    "go to",
    "going to",
    "vacation in",
    "trip to",
    "holiday in",
    "travel to",
)


def _normalize_tokens(query: str) -> list[str]:
    return re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)?", query.lower())


def _has_constraint(query: str, tokens: list[str]) -> bool:
    constraint_words = {
        "under",
        "below",
        "between",
        "around",
        "budget",
        "lightweight",
        "waterproof",
        "durable",
        "portable",
        "size",
        "brand",
        "feature",
        "features",
        "color",
        "material",
    }
    has_number = bool(re.search(r"[$₹€£]?\d+", query))
    return has_number or any(token in constraint_words or token in _FEATURE_HINTS for token in tokens)


def _is_likely_vague(query: str, history: list | None = None) -> bool:
    tokens = _normalize_tokens(query)
    if not tokens:
        return True

    # If the user has already answered clarifying questions in the conversation,
    # avoid forcing another vague classification loop.
    if history and len(history) >= 2:
        recent_user_messages = [
            safe_get(msg, "content", "").strip().lower()
            for msg in history
            if safe_get(msg, "role", "") == "user"
        ]
        if len(recent_user_messages) >= 2:
            return False

    has_product = any(token in _PRODUCT_TERMS for token in tokens)
    has_activity = any(token in _ACTIVITY_TERMS for token in tokens)
    has_constraint = _has_constraint(query, tokens)
    lowered_query = query.lower().strip()
    has_travel_intent = any(phrase in lowered_query for phrase in _TRAVEL_INTENT_PHRASES)

    starts_broad = lowered_query.startswith((
        "i am",
        "i'm",
        "going for",
        "going to",
        "i need",
        "need",
        "want",
        "looking for",
        "suggest",
        "recommend",
        "help me choose",
    ))

    if has_activity and not has_product:
        return True

    if has_travel_intent and not has_product:
        return True

    if len(tokens) <= 5 and not has_constraint and (starts_broad or not has_product):
        return True

    return False

async def _classify_with_groq(messages: list[dict], settings) -> VaguenessResult:
    api_key = safe_get(settings, "GROQ_API_KEY", "")
    if not api_key: 
        raise VaguenessServiceError("No Groq Key")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": safe_get(settings, "GROQ_MODEL", "llama-3.3-70b-versatile"), 
                "messages": messages, 
                "temperature": 0
            },
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        try:
            data = json.loads(content[content.find("{"):content.rfind("}")+1])
            return VaguenessResult(
                classification=data.get("classification", "CLEAR"),
                follow_ups=data.get("follow_ups", []),
                provider="Groq"
            )
        except Exception:
            return VaguenessResult(classification="CLEAR", provider="Groq")

async def _classify_with_gemini(messages: list[dict], settings) -> VaguenessResult:
    api_key = safe_get(settings, "GEMINI_API_KEY", "")
    if not api_key: 
        raise VaguenessServiceError("No Gemini Key")
    
    gemini_payload = {
        "contents": [{"role": "user", "parts": [{"text": m["content"]}]} for m in messages if m["role"] != "system"]
    }
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        response = await client.post(url, json=gemini_payload)
        response.raise_for_status()
        text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        try:
            data = json.loads(text[text.find("{"):text.rfind("}")+1])
            return VaguenessResult(classification=data.get("classification", "CLEAR"), follow_ups=data.get("follow_ups", []), provider="Gemini")
        except Exception:
            return VaguenessResult(classification="CLEAR", provider="Gemini")

async def classify_vagueness(query: str, history: list | None = None, allow_fallback: bool = True) -> VaguenessResult:
    settings = get_settings()

    if _is_likely_vague(query, history=history):
        return VaguenessResult(
            classification="VAGUE",
            follow_ups=[],
            provider="Heuristic",
        )

    messages = build_vagueness_prompt(query, history=history)

    providers = [("Groq", _classify_with_groq), ("Gemini", _classify_with_gemini)]
    
    for name, fn in providers:
        try:
            return await fn(messages, settings)
        except Exception as e:
            logger.warning(f"Provider {name} failed: {e}")
            continue
    
    return VaguenessResult(classification="CLEAR", provider="Fallback")
