"""Chat mode follow-up service for context-aware post-recommendation Q&A."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.config.settings import get_settings
from app.core.logger import get_logger

logger = get_logger(__name__)


def _extract_products(categories_payload: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    flattened: list[dict[str, str]] = []
    for category in categories_payload or []:
        category_name = str(category.get("category") or "General").strip() or "General"
        for product in category.get("products") or []:
            flattened.append(
                {
                    "category": category_name,
                    "title": str(product.get("title") or "").strip(),
                    "price": str(product.get("price") or "").strip(),
                    "reason": str(product.get("explanation") or "").strip(),
                    "label": str(product.get("label") or "").strip(),
                    "url": str(product.get("url") or "").strip(),
                }
            )
    return [item for item in flattened if item["title"]]


def _tokenize(text: str) -> set[str]:
    return {part for part in re.split(r"[^a-z0-9]+", text.lower()) if len(part) > 2}


def _parse_price_to_number(price_text: str) -> float | None:
    digits = re.sub(r"[^\d.]", "", price_text or "")
    if not digits:
        return None
    try:
        return float(digits)
    except ValueError:
        return None


def _heuristic_chat_answer(question: str, products: list[dict[str, str]]) -> str:
    if not products:
        return "I do not have recommendation results in this session yet. Please run a product query first."

    question_lc = question.lower()
    q_tokens = _tokenize(question_lc)

    if any(term in question_lc for term in ["waterproof", "water resistant", "rain", "wet"]):
        matches = [
            product
            for product in products
            if any(term in f"{product['title']} {product['reason']}".lower() for term in ["waterproof", "water resistant", "rain"])
        ]
        if matches:
            top = matches[0]
            return (
                f"Based on the current recommendations, \"{top['title']}\" in {top['category']} looks waterproof-friendly. "
                f"Why: {top['reason'] or 'its listing highlights weather protection.'}"
            )

    if any(term in question_lc for term in ["cheap", "budget", "affordable", "lowest price", "cheapest"]):
        priced = [(product, _parse_price_to_number(product["price"])) for product in products]
        priced = [(product, price) for product, price in priced if price is not None]
        if priced:
            cheapest, _ = sorted(priced, key=lambda item: item[1])[0]
            return (
                f"The most budget-friendly option appears to be \"{cheapest['title']}\" in {cheapest['category']} "
                f"at about {cheapest['price'] or 'an available listed price'}."
            )

    if any(term in question_lc for term in ["best", "top", "highest"]):
        labeled = [product for product in products if product["label"].lower().startswith("best")]
        choice = labeled[0] if labeled else products[0]
        return (
            f"A strong top pick is \"{choice['title']}\" in {choice['category']}. "
            f"Reason: {choice['reason'] or 'it is ranked highly for your use case.'}"
        )

    scored: list[tuple[int, dict[str, str]]] = []
    for product in products:
        text = f"{product['title']} {product['reason']} {product['category']}".lower()
        score = sum(1 for token in q_tokens if token in text)
        scored.append((score, product))
    scored.sort(key=lambda item: item[0], reverse=True)
    top_matches = [item[1] for item in scored[:3] if item[0] > 0]

    if top_matches:
        lines = []
        for idx, match in enumerate(top_matches, start=1):
            lines.append(
                f"{idx}. {match['title']} ({match['category']}) - {match['reason'] or 'fits your stated needs.'}"
            )
        return "Here are the most relevant options from your current results:\n" + "\n".join(lines)

    first = products[0]
    return (
        f"From the current results, start with \"{first['title']}\" in {first['category']}. "
        "If you want, ask about waterproofing, budget, weight, durability, or comfort and I will narrow it down."
    )


def _build_llm_prompt(question: str, products: list[dict[str, str]], profile_context: dict[str, Any] | None) -> str:
    compact_products = products[:20]
    profile_line = ""
    if profile_context:
        profile_line = (
            f"User profile: gender={profile_context.get('gender')}, age={profile_context.get('age')}, "
            f"interests={profile_context.get('interests')}\n"
        )

    return (
        "You are RecommendMe chat mode assistant. Answer only using the provided recommendation context. "
        "If data is missing, say what is missing briefly. Keep answer concise and actionable.\n"
        f"{profile_line}"
        f"User question: {question}\n"
        f"Recommended products JSON: {json.dumps(compact_products, ensure_ascii=True)}"
    )


async def _try_groq(prompt: str, settings) -> str | None:
    if not settings.GROQ_API_KEY:
        return None
    models = [*(settings.GROQ_MODELS or []), settings.GROQ_MODEL, "gpt-oss-120b", "llama-3.3-70b-versatile"]
    seen: set[str] = set()
    candidates = [model for model in models if model and not (model in seen or seen.add(model))][:4]

    headers = {"Authorization": f"Bearer {settings.GROQ_API_KEY}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=8.0) as client:
        for model in candidates:
            try:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers=headers,
                    json={
                        "model": model,
                        "temperature": 0.2,
                        "messages": [
                            {"role": "system", "content": "Answer accurately using provided context only."},
                            {"role": "user", "content": prompt},
                        ],
                    },
                )
                response.raise_for_status()
                content = response.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                if content:
                    return content
            except Exception as exc:
                logger.warning("Chat mode Groq model failed model=%s error=%s", model, str(exc)[:160])
    return None


async def _try_openai(prompt: str, settings) -> str | None:
    if not settings.OPENAI_API_KEY:
        return None
    try:
        from openai import AsyncOpenAI
    except Exception:
        return None

    models = [*(settings.OPENAI_MODELS or []), settings.OPENAI_MODEL, "gpt-4.1", "gpt-4o"]
    seen: set[str] = set()
    candidates = [model for model in models if model and not (model in seen or seen.add(model))][:4]

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, timeout=8.0)
    for model in candidates:
        try:
            completion = await client.chat.completions.create(
                model=model,
                temperature=0.2,
                messages=[
                    {"role": "system", "content": "Answer accurately using provided context only."},
                    {"role": "user", "content": prompt},
                ],
            )
            content = (completion.choices[0].message.content or "").strip()
            if content:
                return content
        except Exception as exc:
            logger.warning("Chat mode OpenAI model failed model=%s error=%s", model, str(exc)[:160])
    return None


async def _try_gemini(prompt: str, settings) -> str | None:
    if not settings.GEMINI_API_KEY:
        return None

    models = [*(settings.GEMINI_MODELS or []), settings.GEMINI_MODEL, "gemini-2.5-flash", "gemini-2.0-flash"]
    seen: set[str] = set()
    candidates = [model for model in models if model and not (model in seen or seen.add(model))][:4]

    async with httpx.AsyncClient(timeout=8.0) as client:
        for model in candidates:
            try:
                response = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={settings.GEMINI_API_KEY}",
                    json={
                        "contents": [
                            {"role": "user", "parts": [{"text": prompt}]},
                        ]
                    },
                )
                response.raise_for_status()
                content = response.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                if content:
                    return content
            except Exception as exc:
                logger.warning("Chat mode Gemini model failed model=%s error=%s", model, str(exc)[:160])
    return None


async def _try_ollama(prompt: str, settings) -> str | None:
    models = [*(settings.OLLAMA_MODELS or []), settings.OLLAMA_MODEL, "phi3", "phi3:latest"]
    seen: set[str] = set()
    candidates = [model for model in models if model and not (model in seen or seen.add(model))][:4]

    async with httpx.AsyncClient(timeout=8.0) as client:
        for model in candidates:
            try:
                response = await client.post(
                    f"{settings.OLLAMA_URL.rstrip('/')}/api/generate",
                    json={"model": model, "prompt": prompt, "stream": False},
                )
                response.raise_for_status()
                content = response.json().get("response", "").strip()
                if content:
                    return content
            except Exception as exc:
                logger.warning("Chat mode Ollama model failed model=%s error=%s", model, str(exc)[:160])
    return None


async def answer_chat_followup(
    *,
    question: str,
    categories_payload: list[dict[str, Any]] | None,
    profile_context: dict[str, Any] | None = None,
) -> str:
    """Return context-aware answer for a post-recommendation chat mode question."""
    products = _extract_products(categories_payload)
    heuristic = _heuristic_chat_answer(question, products)

    settings = get_settings()
    prompt = _build_llm_prompt(question, products, profile_context)

    for provider_name, provider_fn in (
        ("groq", _try_groq),
        ("openai", _try_openai),
        ("gemini", _try_gemini),
        ("ollama", _try_ollama),
    ):
        try:
            content = await provider_fn(prompt, settings)
            if content:
                logger.info("Chat mode answered via %s", provider_name)
                return content
        except Exception as exc:
            logger.warning("Chat mode provider failed provider=%s error=%s", provider_name, str(exc)[:160])

    logger.info("Chat mode using heuristic fallback")
    return heuristic
