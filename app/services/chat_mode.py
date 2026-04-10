"""Chat mode follow-up service for context-aware post-recommendation Q&A."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.config.settings import get_settings
from app.core.logger import get_logger

logger = get_logger(__name__)


def _extract_products(product_types_payload: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    """Extract flattened product list from either new product_types or legacy categories payload."""
    flattened: list[dict[str, str]] = []
    for pt in product_types_payload or []:
        # Support both new schema (product_type/description/product_items)
        # and legacy schema (category/why_needed/products)
        pt_name = str(
            pt.get("product_type") or pt.get("category") or "General"
        ).strip() or "General"
        pt_description = str(pt.get("description") or pt.get("why_needed") or "").strip()
        # Use product_items (new) or products (legacy)
        items = pt.get("product_items") or pt.get("products") or []
        for product in items:
            flattened.append(
                {
                    "product_type": pt_name,
                    "category": pt_name,  # legacy compat
                    "type_description": pt_description,
                    "title": str(product.get("title") or "").strip(),
                    "price": str(product.get("price") or "").strip(),
                    "reason": str(product.get("explanation") or "").strip(),
                    "label": str(product.get("label") or "").strip(),
                    "url": str(product.get("url") or "").strip(),
                    "rating": str(product.get("rating") or "").strip(),
                    "brand": str(product.get("brand") or "").strip(),
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


def _detect_domain(products: list[dict[str, str]]) -> str:
    """Infer the domain from the product categories in the session context."""
    categories_text = " ".join(p.get("category", "").lower() for p in products)
    if any(kw in categories_text for kw in ["movie", "film", "show", "series", "book", "game", "music", "stream", "watch"]):
        return "entertainment"
    if any(kw in categories_text for kw in ["tool", "app", "software", "platform", "saas", "crm", "ide", "plugin"]):
        return "software"
    if any(kw in categories_text for kw in ["trip", "destination", "hotel", "flight", "travel", "tour", "trek", "hike"]):
        return "travel"
    if any(kw in categories_text for kw in ["recipe", "dish", "meal", "food", "ingredient", "cook", "restaurant"]):
        return "food"
    return "shopping"


def _heuristic_chat_answer(question: str, products: list[dict[str, str]]) -> str:
    if not products:
        return "I do not have recommendation results in this session yet. Please run a product query first."

    question_lc = question.lower()
    q_tokens = _tokenize(question_lc)
    domain = _detect_domain(products)

    # ── Domain-specific heuristics ────────────────────────────────────────────

    if domain == "entertainment":
        if any(t in question_lc for t in ["mood", "feel", "tone", "vibe"]):
            top = products[0]
            return (
                f"Based on your preferences, \"{top['title']}\" fits well. "
                f"{top['reason'] or 'It matches the tone and style you described.'}"
            )
        if any(t in question_lc for t in ["platform", "stream", "watch on", "available on"]):
            matches = [p for p in products if any(s in f"{p['title']} {p['reason']}".lower() for s in ["netflix", "prime", "hulu", "disney", "hotstar", "youtube"])]
            if matches:
                return f"\"{matches[0]['title']}\" should be available on a streaming platform. {matches[0]['reason'] or ''}"
            return "I don't have streaming platform details in the current results — check the link for availability."
        if any(t in question_lc for t in ["short", "long", "runtime", "quick", "episode"]):
            top = products[0]
            return f"From current picks, \"{top['title']}\" is a solid choice. {top['reason'] or 'Check runtime on the listing page.'}"

    elif domain == "software":
        if any(t in question_lc for t in ["free", "cost", "price", "cheap", "affordable", "open source"]):
            priced = [(p, _parse_price_to_number(p["price"])) for p in products]
            priced = [(p, pr) for p, pr in priced if pr is not None]
            if priced:
                cheapest, _ = sorted(priced, key=lambda x: x[1])[0]
                return f"The most affordable option appears to be \"{cheapest['title']}\" at {cheapest['price']}. {cheapest['reason'] or ''}"
            free_candidates = [p for p in products if "free" in f"{p['title']} {p['reason']}".lower()]
            if free_candidates:
                return f"\"{free_candidates[0]['title']}\" may have a free tier. Check the listing for details."
        if any(t in question_lc for t in ["integrate", "integration", "api", "connect", "compatible"]):
            top = products[0]
            return f"\"{top['title']}\" likely supports integrations — {top['reason'] or 'check the docs for compatibility details.'}"
        if any(t in question_lc for t in ["best", "top", "recommended"]):
            labeled = [p for p in products if p["label"].lower().startswith("best")]
            choice = labeled[0] if labeled else products[0]
            return f"A strong choice is \"{choice['title']}\". {choice['reason'] or 'It ranked highest for your use case.'}"

    elif domain == "travel":
        if any(t in question_lc for t in ["budget", "cheap", "affordable", "cost", "price"]):
            priced = [(p, _parse_price_to_number(p["price"])) for p in products]
            priced = [(p, pr) for p, pr in priced if pr is not None]
            if priced:
                cheapest, _ = sorted(priced, key=lambda x: x[1])[0]
                return f"A budget-friendly option is \"{cheapest['title']}\" at {cheapest['price']}. {cheapest['reason'] or ''}"
        if any(t in question_lc for t in ["solo", "alone", "group", "family", "couple"]):
            top = products[0]
            return f"\"{top['title']}\" works well for your group type. {top['reason'] or 'It accommodates various traveler profiles.'}"
        if any(t in question_lc for t in ["best", "top", "recommend"]):
            top = products[0]
            return f"A top pick is \"{top['title']}\". {top['reason'] or 'Highly rated for your destination type.'}"

    elif domain == "food":
        if any(t in question_lc for t in ["quick", "fast", "easy", "simple", "30 minute", "15 minute"]):
            top = products[0]
            return f"For a quick option, try \"{top['title']}\". {top['reason'] or 'It is simple and takes minimal prep time.'}"
        if any(t in question_lc for t in ["vegetarian", "vegan", "gluten", "dairy", "allergy", "diet"]):
            matches = [p for p in products if any(kw in f"{p['title']} {p['reason']}".lower() for kw in ["vegetarian", "vegan", "gluten-free", "dairy-free"])]
            if matches:
                return f"\"{matches[0]['title']}\" fits dietary preferences. {matches[0]['reason'] or ''}"

    else:
        # Shopping domain — original logic preserved
        if any(t in question_lc for t in ["waterproof", "water resistant", "rain", "wet"]):
            matches = [p for p in products if any(t in f"{p['title']} {p['reason']}".lower() for t in ["waterproof", "water resistant", "rain"])]
            if matches:
                top = matches[0]
                return (
                    f"Based on the current recommendations, \"{top['title']}\" in {top['category']} looks waterproof-friendly. "
                    f"Why: {top['reason'] or 'its listing highlights weather protection.'}"
                )
        if any(t in question_lc for t in ["cheap", "budget", "affordable", "lowest price", "cheapest"]):
            priced = [(p, _parse_price_to_number(p["price"])) for p in products]
            priced = [(p, pr) for p, pr in priced if pr is not None]
            if priced:
                cheapest, _ = sorted(priced, key=lambda x: x[1])[0]
                return (
                    f"The most budget-friendly option appears to be \"{cheapest['title']}\" in {cheapest['category']} "
                    f"at about {cheapest['price'] or 'an available listed price'}."
                )
        if any(t in question_lc for t in ["best", "top", "highest"]):
            labeled = [p for p in products if p["label"].lower().startswith("best")]
            choice = labeled[0] if labeled else products[0]
            return (
                f"A strong top pick is \"{choice['title']}\" in {choice['category']}. "
                f"Reason: {choice['reason'] or 'it is ranked highly for your use case.'}"
            )

    # ── General token-matching fallback (all domains) ─────────────────────────
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
    domain_tips = {
        "entertainment": "genre, mood, runtime, or platform",
        "software": "pricing, integrations, team size, or use case",
        "travel": "budget, group size, duration, or destination type",
        "food": "diet, prep time, cuisine, or ingredients",
        "shopping": "waterproofing, budget, weight, durability, or comfort",
    }
    tip = domain_tips.get(domain, "specific requirements")
    return (
        f"From the current results, start with \"{first['title']}\" in {first['category']}. "
        f"If you want, ask about {tip} and I will narrow it down."
    )



def _build_llm_prompt(
    question: str,
    products: list[dict[str, str]],
    profile_context: dict[str, Any] | None,
    *,
    original_query: str | None = None,
    clarification_answers: list[dict[str, str]] | None = None,
    session_category: str | None = None,
    product_type_descriptions: list[dict[str, str]] | None = None,
) -> str:
    """Build the full-context prompt for chat mode (Flow.md §8).

    Flow.md requires the AI to receive:
    - Initial user query
    - All 5 follow-up questions and user responses
    - Generated category and all product type descriptions
    - All product items retrieved from SERP
    - User profile / settings data (if logged in)
    """
    compact_products = products[:20]

    profile_line = ""
    if profile_context:
        profile_line = (
            f"User profile: gender={profile_context.get('gender')}, age={profile_context.get('age')}, "
            f"interests={profile_context.get('interests')}\n"
        )

    original_query_line = ""
    if original_query:
        original_query_line = f"Original user query: {original_query}\n"

    qa_context = ""
    if clarification_answers:
        qa_pairs = "\n".join(
            f"  Q: {pair.get('question', '')}\n  A: {pair.get('answer', '')}"
            for pair in clarification_answers
        )
        qa_context = f"Follow-up Q&A context:\n{qa_pairs}\n"

    category_line = ""
    if session_category:
        category_line = f"Session category: {session_category}\n"

    type_desc_context = ""
    if product_type_descriptions:
        desc_lines = "\n".join(
            f"  - {d.get('product_type', '')}: {d.get('description', '')}"
            for d in product_type_descriptions[:10]
        )
        type_desc_context = f"Product type descriptions:\n{desc_lines}\n"

    return (
        "You are RecommendMe chat mode assistant. Answer ONLY using the provided recommendation context. "
        "Reference specific products, prices, and details from the context. "
        "If data is missing, say what is missing briefly. Keep the answer concise and actionable.\n\n"
        f"{profile_line}"
        f"{original_query_line}"
        f"{qa_context}"
        f"{category_line}"
        f"{type_desc_context}"
        f"User question: {question}\n"
        f"Recommended products (JSON): {json.dumps(compact_products, ensure_ascii=True)}"
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
    original_query: str | None = None,
    clarification_answers: list[dict[str, Any]] | None = None,
    session_category: str | None = None,
) -> str:
    """Return context-aware answer for a post-recommendation chat mode question.

    Flow.md §8 — Full context is passed to the AI on every chat message:
    - Initial user query
    - All 5 follow-up questions and user responses
    - Generated category and all product type descriptions
    - All product items retrieved from SERP
    - User profile / settings data
    """
    products = _extract_products(categories_payload)
    heuristic = _heuristic_chat_answer(question, products)

    # Build product type descriptions list for the prompt
    product_type_descriptions: list[dict[str, str]] = []
    for pt in categories_payload or []:
        pt_name = str(pt.get("product_type") or pt.get("category") or "").strip()
        pt_desc = str(pt.get("description") or pt.get("why_needed") or "").strip()
        if pt_name:
            product_type_descriptions.append({"product_type": pt_name, "description": pt_desc})

    settings = get_settings()
    prompt = _build_llm_prompt(
        question,
        products,
        profile_context,
        original_query=original_query,
        clarification_answers=clarification_answers,
        session_category=session_category,
        product_type_descriptions=product_type_descriptions,
    )

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
