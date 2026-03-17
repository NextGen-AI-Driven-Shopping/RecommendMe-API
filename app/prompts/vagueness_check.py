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

import logging
from dataclasses import dataclass, field
from typing import Literal

logger = logging.getLogger(__name__)

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
You are a precise product-query analyst. Your job:

  1. Decide if a shopping query is CLEAR or VAGUE.
  2. If VAGUE, write exactly 3 follow-up questions that are SPECIFIC to the
     exact words the user typed — never generic boilerplate.

────────────────────────────────────────────
OUTPUT FORMAT  (return ONLY valid JSON, zero markdown)
────────────────────────────────────────────
CLEAR → {"classification": "CLEAR"}
VAGUE → {"classification": "VAGUE", "follow_ups": ["Q1", "Q2", "Q3"]}

────────────────────────────────────────────
WHEN IS A QUERY CLEAR?
────────────────────────────────────────────
A query is CLEAR when it contains ALL of:
  • A concrete product/category  (e.g. "trail running shoes", "noise-cancelling headphones")
  • At least ONE of:
      – primary use-case         (gaming, hiking, office work …)
      – environment / terrain    (rain, high-altitude, indoors …)
      – a meaningful constraint  (under ₹5000, waterproof, lightweight …)
      – a meaningful preference  (wireless, size M, carbon-fibre frame …)

Single-word or two-word bare nouns with no qualifiers are always VAGUE.

────────────────────────────────────────────
HOW TO WRITE GOOD FOLLOW-UP QUESTIONS
────────────────────────────────────────────
RULE 1 — ANCHOR TO THE QUERY'S OWN WORDS
  Every question must reference a specific noun, verb, or adjective the
  user actually typed. Never ask a question that would fit any shopping
  query (e.g. "What's your budget?" as a first question).

RULE 2 — PRIORITY ORDER
  ① Narrow the activity / use-case   (most discriminating)
  ② Narrow the environment / context
  ③ Narrow a decision-fork specific to that product space

RULE 3 — BINARY OR SMALL-SET OPTIONS WHERE HELPFUL
  Offering 2–3 concrete options inside the question is often better than
  asking an open-ended one.
  Good: "Will these be for road running, trail running, or gym use?"
  Bad:  "What will you use them for?"

RULE 4 — LENGTH  ≤ 15 words per question, conversational tone.

RULE 5 — NEVER ASK THESE AS Q1
  ✗ "What is your budget?"
  ✗ "What brand do you prefer?"
  ✗ "Solo or group?"
  ✗ "Male or female?" (unless the query mentions gender)

────────────────────────────────────────────
WORKED EXAMPLES  (study the derivation logic, do NOT copy the questions)
────────────────────────────────────────────

Query: "trekking"
→ VAGUE
  The word "trekking" tells us nothing about duration, terrain, or gear scope.
  Q1: "Are you planning day hikes, multi-day trips, or high-altitude expeditions?"
  Q2: "Which terrain — rocky mountain trails, forest paths, or desert routes?"
  Q3: "Looking for a single item (boots, bag) or a complete starter kit?"

  ❌ BAD (do NOT produce):
  "What type of trekking?" — echoes the query word, narrows nothing
  "Which region or climate?" — generic enough to fit any outdoor query

Query: "running shoes"
→ VAGUE
  Q1: "Road running, trail running, or track/gym use?"
  Q2: "Do you overpronate, underpronate, or run with a neutral gait?"
  Q3: "Priority — max cushioning for long distances, or lightweight speed shoes?"

Query: "headphones"
→ VAGUE
  Q1: "Main use — commuting, studio monitoring, gaming, or work calls?"
  Q2: "Over-ear, on-ear, or in-ear form factor?"
  Q3: "Wireless with ANC, or wired for audio fidelity?"

Query: "laptop"
→ VAGUE
  Q1: "Primary workload — dev/coding, video editing, gaming, or general use?"
  Q2: "Windows, macOS, or Linux?"
  Q3: "Compact 13–14″ for portability, or 15–16″ for screen space?"

Query: "camping tent"
→ VAGUE
  Q1: "Solo, 2-person, or family/group tent?"
  Q2: "3-season backpacking tent or car-camping base tent?"
  Q3: "Ultralight for trekking, or spacious comfort over weight?"

Query: "gaming laptop under ₹80,000"
→ CLEAR  (product + use-case + price constraint)

Query: "waterproof trail running shoes size 10"
→ CLEAR  (product + terrain + spec + size)

────────────────────────────────────────────
INTERNAL DERIVATION CHECKLIST (do not output this)
────────────────────────────────────────────
Before writing each question ask:
  • Which specific word(s) in the query prompted this question?
  • Does the answer meaningfully fork the product space?
  • Could this question apply to almost any shopping query? → rewrite if yes.
"""


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def build_vagueness_prompt(
    query: str,
    context: list[dict[str, str]] | None = None,
) -> Messages:
    """
    Build the message list for a vagueness-classification LLM call.

    The system prompt is injected as the first message (role ``"system"``),
    compatible with the OpenAI chat format.  Anthropic callers should pop it
    out and pass it as the top-level ``system`` parameter.

    Args:
        query:   The raw user search string.  Must be non-empty.
        context: Optional prior conversation turns for multi-turn context.

    Returns:
        Ordered list of chat messages ready for any chat-completion API.

    Raises:
        ValueError: If *query* is blank or whitespace-only.
    """
    if not query or not query.strip():
        raise ValueError("query must be a non-empty string")

    messages: Messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if context:
        messages.extend(context)

    messages.append({"role": "user", "content": query.strip()})
    return messages