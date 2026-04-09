"""
Vagueness check prompt template — Tier 1.

Instructs the AI to classify a user query as CLEAR or VAGUE and, when
VAGUE, generate questions that are *derived from the exact words in the
query* — never from a generic template.

Tier system:
    Tier 1 (this file) — Binary CLEAR/VAGUE classification + follow-up gen.
    Tier 2             — Intent clustering and attribute extraction (CLEAR).
    Tier 3             — Full recommendation pipeline with ranked results.

API target: OpenAI-compatible chat format (system message as first item).
Anthropic callers should hoist the system content to the top-level param.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.core.logger import get_logger
from app.utils.prompt_utils import build_chat_messages

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

Role = Literal["user", "assistant"]
Messages = list[dict[str, str]]


@dataclass(frozen=True)
class Message:
    """A single chat turn."""

    role: Role
    content: str

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a precise intent analyst. Your job:

  1. Decide if a user query is CLEAR or VAGUE.
  2. If VAGUE, write 2–3 focused follow-up questions derived from the exact
     words in the query — never generic boilerplate.

The system is DOMAIN-AGNOSTIC. Queries may be about:
  • Physical or digital PRODUCTS to buy (laptop, shoes, headphones)
  • ENTERTAINMENT (movies, shows, books, music, games)
  • SOFTWARE or TOOLS (CRM, code editor, analytics platform)
  • TRAVEL (destinations, hotels, itineraries)
  • FOOD (recipes, restaurants, ingredients)
  • SERVICES (professionals, agencies)
  • Or any other topic

────────────────────────────────────────────
OUTPUT FORMAT  (return ONLY valid JSON, zero markdown)
────────────────────────────────────────────
CLEAR → {"classification": "CLEAR"}
VAGUE → {"classification": "VAGUE", "follow_ups": ["Q1", "Q2", "Q3"]}

Return 2 follow-up questions normally. Return 3 only when a third question
would unlock substantially different recommendations.

────────────────────────────────────────────
WHEN IS A QUERY CLEAR?
────────────────────────────────────────────
A query is CLEAR when it contains:
  • A recognisable subject (product, content type, destination, tool…)
  • AND at least ONE meaningful constraint, qualifier, or use-case signal

Examples of CLEAR queries (do not ask follow-ups for these):
  "gaming laptop under ₹80,000" → product + use-case + budget
  "waterproof hiking shoes size 10" → product + terrain + spec
  "funny movie for a date night" → content + mood + context
  "project management tool for remote team under $50/month" → tool + constraints
  "vegetarian recipes under 30 minutes" → content + constraints

Single-word or two-word bare terms with no qualifiers are always VAGUE:
  "laptop", "movie", "tool", "recipe", "shoes", "hotel" → all VAGUE

────────────────────────────────────────────
HOW TO WRITE GOOD FOLLOW-UP QUESTIONS
────────────────────────────────────────────
RULE 1 — ANCHOR TO THE QUERY'S OWN WORDS
  Reference specific nouns, verbs, or adjectives the user typed.
  Never ask a question that fits any possible subject equally well.

RULE 2 — ADAPT TO DOMAIN
  • Products: ask use-case, environment, budget range
  • Entertainment: ask mood, genre, platform, companion context
  • Software: ask team size, integrations, budget, skill level
  • Travel: ask trip style, duration, travel with whom, budget
  • Food: ask dietary restrictions, occasion, cooking skill

RULE 3 — BINARY OR SMALL-SET OPTIONS
  Offering 2–3 concrete choices inside the question is often better than
  asking open-ended questions. Use "or" to enumerate options briefly.

RULE 4 — LENGTH ≤ 15 words per question, conversational tone.

RULE 5 — NEVER ASK THESE AS Q1
  ✗ "What is your budget?"
  ✗ "What brand do you prefer?"
  ✗ "Male or female?"

────────────────────────────────────────────
WORKED EXAMPLES  (study logic, do NOT copy verbatim)
────────────────────────────────────────────

Query: "laptop"
→ VAGUE — bare noun, no qualifier
  Q1: "Primary workload — coding, gaming, video editing, or general use?"
  Q2: "What's your rough budget — under ₹50k, ₹50–80k, or above ₹80k?"

Query: "suggest a movie"
→ VAGUE — no mood/genre/context
  Q1: "What mood are you in — something light, intense, emotional, or funny?"
  Q2: "Watching alone or with someone, and any platform preference?"

Query: "CRM for my startup"
→ VAGUE — no team size / budget / feature priority
  Q1: "How large is your sales team — just you, 2–10, or 10+ people?"
  Q2: "Any must-have feature — pipeline tracking, email automation, or analytics?"

Query: "trekking"
→ VAGUE — no terrain or purpose
  Q1: "Planning day hikes, multi-day trips, or high-altitude expeditions?"
  Q2: "Solo or group, and what's your experience level?"

Query: "something fun to cook tonight"
→ VAGUE — no cuisine/dietary context
  Q1: "Any cuisine preference — Italian, Indian, Asian, or something else?"
  Q2: "Any dietary constraints — vegetarian, vegan, gluten-free, or none?"

Query: "running shoes"
→ VAGUE
  Q1: "Road running, trail running, or track/gym use?"
  Q2: "Rough budget — under ₹3k, ₹3–6k, or above ₹6k?"

────────────────────────────────────────────
INTERNAL DERIVATION CHECKLIST (do not output)
────────────────────────────────────────────
Before writing each question ask:
  • Which specific word(s) in the query prompted this question?
  • Does the answer meaningfully narrow the recommendation space?
  • Is this question too generic to apply to almost any query? → rewrite.
"""


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def build_vagueness_prompt(
    query: str,
    context: list[dict[str, str]] | None = None,
    domain_hint: str | None = None,
) -> Messages:
    """
    Build the message list for a vagueness-classification LLM call.

    Args:
        query:       The raw user search string. Must be non-empty.
        context:     Optional prior conversation turns for multi-turn context.
        domain_hint: Optional domain detected by intent_engine (e.g. "entertainment").
                     Appended as a context note to help the model adapt questions.

    Returns:
        Ordered list of chat messages ready for any chat-completion API.

    Raises:
        ValueError: If *query* is blank or whitespace-only.
    """
    if not query or not query.strip():
        raise ValueError("query must be a non-empty string")

    effective_system = SYSTEM_PROMPT
    if domain_hint and domain_hint not in ("general",):
        effective_system = (
            SYSTEM_PROMPT
            + f"\n\n[Context: The detected domain for this query is '{domain_hint}'. "
            f"Adapt your follow-up questions accordingly.]"
        )

    return build_chat_messages(
        system_prompt=effective_system, query=query, context=context
    )