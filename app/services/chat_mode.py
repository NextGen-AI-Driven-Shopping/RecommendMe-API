"""
Post-recommendation chat mode service (Step 8 of Flow.md).

Handles follow-up questions after recommendations are displayed.
The AI answers the question AND declares which specific products it picked,
so the route can filter session products down to only those items.
"""

from __future__ import annotations

import os
import re

import httpx

from app.config.settings import get_settings
from app.core.logger import get_logger
from app.services.vagueness import _try_provider_chain

logger = get_logger(__name__)

# ── System prompt ─────────────────────────────────────────────────────────────

CHAT_SYSTEM_PROMPT = """\
You are a product recommendation assistant answering follow-up questions.

The user has ALREADY received recommendations. The full list is in \
<RECOMMENDED_PRODUCTS> below.

ABSOLUTE RULES:
1. ONLY reference products explicitly listed in <RECOMMENDED_PRODUCTS>.
2. Do NOT fabricate prices, ratings, or specs.
3. For "top N", "best N", "pick N" requests — pick EXACTLY N products
   from the ENTIRE list across ALL categories combined, ranked by
   overall value (rating + price + specs). Do NOT pick N per category.
4. <selected> must contain EXACTLY those N names, pipe-separated.
5. For general questions — leave <selected> empty.

RESPONSE FORMAT:
<answer>
[One short sentence max. For ranking queries just say "Here are the top N picks."]
</answer>
<selected>
[Pipe-separated EXACT product names, best first. Empty for general answers.]
</selected>
"""


# ── Slim context builder ──────────────────────────────────────────────────────
# IMPORTANT: We intentionally send ONLY name + price + rating to the AI.
# Sending full descriptions + links caused 413 Payload Too Large on Groq
# when there were 100 products (10 types × 10 items).
# The AI only needs names to pick from — the frontend already has full data.

def _build_slim_product_block(product_types_data: list[dict]) -> str:
    """
    Render products as a compact reference list.
    Format: #N. Product Name | Price | Rating
    No descriptions, no links, no delivery info — keeps context tiny.
    """
    if not product_types_data:
        return "(No product data available)"

    lines: list[str] = []
    global_index = 1

    for pt in product_types_data:
        pt_name = pt.get("product_type") or pt.get("category") or "Products"
        lines.append(f"\n[{pt_name}]")

        items = pt.get("product_items") or pt.get("products") or []
        if not items:
            lines.append("  (no items)")
            continue

        for item in items:
            name   = item.get("product_name") or item.get("title") or "Unknown"
            price  = item.get("price_inr")    or item.get("price") or "N/A"
            rating = item.get("rating")
            rating_str = f" | ★{rating}/5" if rating is not None else ""
            lines.append(f"  #{global_index}. {name} | {price}{rating_str}")
            global_index += 1

    return "\n".join(lines)


def _build_context_prefix(
    *,
    original_query: str | None,
    category: str | None,
    product_types_data: list[dict],
) -> str:
    parts: list[str] = []

    if original_query:
        parts.append(f'Original request: "{original_query}"')
    if category:
        parts.append(f"Category: {category}")

    product_block = _build_slim_product_block(product_types_data)
    parts.append(f"\n<RECOMMENDED_PRODUCTS>\n{product_block}\n</RECOMMENDED_PRODUCTS>")

    return "\n".join(parts)


# ── Think-block stripper ──────────────────────────────────────────────────────

def _strip_think_blocks(text: str) -> str:
    """
    Remove <think>...</think> reasoning blocks emitted by some models
    (e.g. DeepSeek-R1, QwQ) before the structured response is parsed.
    Also handles unclosed <think> tags that run to end of string.
    """
    # Remove closed blocks: <think>...</think>
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    # Remove unclosed blocks: <think>... to end of string
    text = re.sub(r"<think>.*",          "", text, flags=re.DOTALL | re.IGNORECASE)
    return text.strip()


# ── Response parser ───────────────────────────────────────────────────────────

def _parse_structured_response(raw: str) -> tuple[str, list[str]]:
    """
    Parse <answer>...</answer><selected>...</selected> from AI response.

    Returns:
        (answer_text, selected_product_names)
        selected_product_names is [] if AI picked no specific products.
    """
    # Strip any think blocks before parsing so they don't pollute the answer
    raw = _strip_think_blocks(raw)

    answer_match  = re.search(r"<answer>(.*?)</answer>",   raw, re.DOTALL | re.IGNORECASE)
    selected_match = re.search(r"<selected>(.*?)</selected>", raw, re.DOTALL | re.IGNORECASE)

    if answer_match:
        answer_text = answer_match.group(1).strip()
    else:
        # Fallback: strip <selected> block and use rest as answer
        answer_text = re.sub(
            r"<selected>.*?</selected>", "", raw, flags=re.DOTALL | re.IGNORECASE
        ).strip()

    selected_names: list[str] = []
    if selected_match:
        raw_selected = selected_match.group(1).strip()
        if raw_selected:
            selected_names = [n.strip() for n in raw_selected.split("|") if n.strip()]

    return answer_text, selected_names


# ── Product filter ────────────────────────────────────────────────────────────

def filter_product_types_by_names(
    product_types_data: list[dict],
    selected_names: list[str],
) -> list[dict]:
    """
    Return only product items whose name fuzzy-matches one of selected_names.

    Matching: case-insensitive substring both ways + 60% token overlap fallback.
    If selected_names is empty → return full list (no filter).
    If nothing matches → log warning and return full list as safety net.
    """
    if not selected_names:
        return product_types_data

    def _matches(product_name: str) -> bool:
        pn = product_name.lower()
        for sel in selected_names:
            sl = sel.lower()
            if sl in pn or pn in sl:
                return True
            # Token overlap: ≥60% of selected tokens appear in product name
            sel_tokens = set(sl.split())
            pn_tokens  = set(pn.split())
            if sel_tokens and len(sel_tokens & pn_tokens) / len(sel_tokens) >= 0.6:
                return True
        return False

    filtered: list[dict] = []
    for pt in product_types_data:
        items = pt.get("product_items") or pt.get("products") or []
        matched = [
            item for item in items
            if _matches(item.get("product_name") or item.get("title") or "")
        ]
        if matched:
            filtered.append({**pt, "product_items": matched})

    if not filtered:
        logger.warning(
            "[chat_mode] No products matched selected_names=%s — returning all", selected_names
        )
        return product_types_data

    return filtered


# ── Groq caller ───────────────────────────────────────────────────────────────

_GROQ_TIMEOUT = 20.0
_GROQ_FALLBACK_MODELS = [
    "llama-3.3-70b-versatile",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "mixtral-8x7b-32768",
]


async def _call_groq_direct(messages: list[dict]) -> str | None:
    settings = get_settings()
    api_key = getattr(settings, "GROQ_API_KEY", "") or os.getenv("GROQ_API_KEY", "")
    if not api_key:
        logger.warning("[chat_mode] GROQ_API_KEY not configured")
        return None

    configured: list[str] = list(getattr(settings, "GROQ_MODELS", []) or [])
    candidate_models: list[str] = []
    for m in [*configured, *_GROQ_FALLBACK_MODELS]:
        if m and m not in candidate_models:
            candidate_models.append(m)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    for model in candidate_models[:4]:
        try:
            async with httpx.AsyncClient(timeout=_GROQ_TIMEOUT) as client:
                resp = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers=headers,
                    json={"model": model, "temperature": 0.3, "messages": messages},
                )

            if resp.status_code == 413:
                logger.warning("[chat_mode] Groq/%s → 413 (still too large)", model)
                continue
            if resp.status_code == 429:
                logger.warning("[chat_mode] Groq/%s → 429 rate limited", model)
                continue
            if resp.status_code == 400:
                logger.warning("[chat_mode] Groq/%s → 400: %s", model, resp.text[:200])
                continue

            resp.raise_for_status()
            text = (
                resp.json()
                .get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            if text:
                logger.info("[chat_mode] Groq/%s succeeded", model)
                return text

        except Exception as exc:
            logger.warning("[chat_mode] Groq/%s error: %s", model, str(exc)[:120])

    return None


# ── Main entry point ──────────────────────────────────────────────────────────

_FALLBACK_ERROR = (
    "I'm having trouble answering right now. Please try again in a moment.",
    None,   # None = error state — route will NOT return product cards
)


async def answer_chat_followup(
    *,
    question: str,
    session_data: dict | None = None,
    categories_payload: list[dict] | None = None,
    profile_context: dict | None = None,
) -> tuple[str, list[str] | None]:
    """
    Generate an answer to a follow-up question.

    Returns:
        (answer_text, selected_product_names)

        selected_product_names:
          - list[str]  → names AI picked; filter products to these
          - []         → AI gave a general answer; show all products
          - None       → provider error; show NO product cards
    """
    # ── Build slim product context ────────────────────────────────────────────
    if session_data:
        product_types_data = (
            session_data.get("product_types")
            or (session_data.get("latest_response") or {}).get("product_types")
            or session_data.get("categories")
            or []
        )
        context_prefix = _build_context_prefix(
            original_query=session_data.get("original_query"),
            category=session_data.get("category"),
            product_types_data=product_types_data,
        )
    elif categories_payload:
        context_prefix = _build_context_prefix(
            original_query=None,
            category=None,
            product_types_data=categories_payload,
        )
    else:
        context_prefix = "<RECOMMENDED_PRODUCTS>(No product data)</RECOMMENDED_PRODUCTS>"

    messages = [
        {"role": "system", "content": CHAT_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"{context_prefix}\n\n"
                f"User question: {question}\n\n"
                f"Respond using <answer></answer> and <selected></selected> tags."
            ),
        },
    ]

    raw = await _call_groq_direct(messages)

    if not raw:
        logger.warning("[chat_mode] Direct Groq failed, trying _try_provider_chain")
        raw = await _try_provider_chain(messages, step_name="chat_mode")

    if not raw:
        logger.warning("[chat_mode] All providers failed for question=%s", question[:80])
        return _FALLBACK_ERROR  # None signals "don't show products"

    # Strip think blocks before parsing — some models (DeepSeek-R1, QwQ)
    # emit <think>...</think> reasoning blocks before the actual response.
    clean_raw = _strip_think_blocks(raw.strip())

    answer_text, selected_names = _parse_structured_response(clean_raw)

    logger.info(
        "[chat_mode] answer_len=%d selected_count=%d selected=%s",
        len(answer_text), len(selected_names), selected_names,
    )

    return answer_text, selected_names