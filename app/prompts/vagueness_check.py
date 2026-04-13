"""
Vagueness check prompt template — Step 2 of Flow.md.

Classifies user query into 4 states:
  CLEAR       → Proceed directly to Question Engine (Step 3)
  VAGUE       → Pre-clarification question (Step 2.5)
  AMBIGUOUS   → Pre-clarification question (Step 2.5)
  OUT_OF_SCOPE → Graceful decline

API target: OpenAI-compatible chat format (system message as first item).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.core.logger import get_logger
from app.utils.prompt_utils import build_chat_messages

logger = get_logger(__name__)

Role = Literal["user", "assistant"]
Messages = list[dict[str, str]]


@dataclass(frozen=True)
class Message:
    """A single chat turn."""

    role: Role
    content: str

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


SYSTEM_PROMPT = """\
You are a precise product-query analyst. Your job:

  1. Classify a user query as CLEAR, VAGUE, AMBIGUOUS, or OUT_OF_SCOPE.
  2. Return a JSON response.

────────────────────────────────────────────
OUTPUT FORMAT  (return ONLY valid JSON, zero markdown)
────────────────────────────────────────────

CLEAR →
  {"classification": "CLEAR"}

VAGUE →
  {"classification": "VAGUE"}

AMBIGUOUS →
  {"classification": "AMBIGUOUS"}

OUT_OF_SCOPE →
  {"classification": "OUT_OF_SCOPE", "message": "A friendly explanation of why this is out of scope."}

────────────────────────────────────────────
CLASSIFICATION DEFINITIONS
────────────────────────────────────────────

CLEAR:
  The query contains a concrete product or category PLUS at least one of:
  - Primary use-case (gaming, hiking, office, etc.)
  - Environment / terrain (rain, indoor, mountain, etc.)
  - A meaningful constraint (under ₹5000, waterproof, lightweight, etc.)
  - A meaningful preference (wireless, size M, brand preference, etc.)

VAGUE:
  The query mentions a real product/need but lacks sufficient context.
  Single-word or two-word bare nouns without qualifiers are always VAGUE.
  Examples: "headphones", "laptop", "shoes", "camping gear"

AMBIGUOUS:
  The query has multiple valid interpretations that would lead to
  fundamentally different product recommendations.
  Example: "something for my trip" (business trip? vacation? road trip?)

OUT_OF_SCOPE:
  The query cannot produce product recommendations at all.
  Examples: "what's the weather today", "tell me a joke", "explain quantum physics"
  In this case, add a "message" field with a friendly decline.

────────────────────────────────────────────
EXAMPLES
────────────────────────────────────────────

"gaming laptop under ₹80,000"
  → {"classification": "CLEAR"}

"waterproof trail running shoes size 10"
  → {"classification": "CLEAR"}

"headphones"
  → {"classification": "VAGUE"}

"something for my trip"
  → {"classification": "AMBIGUOUS"}

"tell me a joke"
  → {"classification": "OUT_OF_SCOPE", "message": "I'm a product recommendation assistant! I can help you find the perfect products. Try asking me something like 'best running shoes for marathons' or 'laptop for video editing'."}

"what time is it"
  → {"classification": "OUT_OF_SCOPE", "message": "I specialize in product recommendations. Ask me about any product you're looking for and I'll help you find the best options!"}
"""


def build_vagueness_prompt(
    query: str,
    context: list[dict[str, str]] | None = None,
) -> Messages:
    """
    Build the message list for a vagueness-classification LLM call.

    Args:
        query:   The raw user search string. Must be non-empty.
        context: Optional prior conversation turns for multi-turn context.

    Returns:
        Ordered list of chat messages ready for any chat-completion API.

    Raises:
        ValueError: If *query* is blank or whitespace-only.
    """
    if not query or not query.strip():
        raise ValueError("query must be a non-empty string")

    return build_chat_messages(system_prompt=SYSTEM_PROMPT, query=query, context=context)