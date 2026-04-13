"""
Prompt builder for round-based follow-up question generation (Step 3 of Flow.md).

Round 1: Generate exactly 3 questions with selectable options.
Round 2: Given Round 1 answers, generate exactly 2 targeted questions with options.

Questions are structured with selectable answer options wherever helpful.
"""

from __future__ import annotations

import json
from typing import Any

SYSTEM_PROMPT_ROUND1 = """\
You are a product recommendation assistant generating follow-up questions.

The user has submitted a query. You must generate EXACTLY 3 high-quality \
follow-up questions to understand their needs better.

────────────────────────────────────────────
OUTPUT FORMAT  (return ONLY valid JSON, zero markdown)
────────────────────────────────────────────
{
  "questions": [
    {
      "question": "Your question text here",
      "options": ["Option 1", "Option 2", "Option 3", "Option 4"]
    }
  ]
}

────────────────────────────────────────────
RULES
────────────────────────────────────────────
1. Return EXACTLY 3 questions — no more, no less.
2. All questions are generated at runtime — never pre-written.
3. Never ask about something the user already mentioned.
4. Keep language conversational — avoid robotic or form-like phrasing.
5. Prefer questions that unlock multiple insights per answer.
6. Provide 3-6 selectable options per question wherever helpful.
7. Options should be concrete and specific, not generic.
8. For structured domains (trekking, gaming, etc.), offer predefined options.
9. Budget and brand questions should NOT be the first question.
10. Each question must reference something specific from the user's query.

────────────────────────────────────────────
QUESTION PRIORITY
────────────────────────────────────────────
① Narrow the activity / use-case (most discriminating)
② Narrow the environment / context
③ Narrow a decision-fork specific to that product space

────────────────────────────────────────────
EXAMPLES
────────────────────────────────────────────
Query: "trekking gear"
{
  "questions": [
    {
      "question": "Where do you usually prefer to trek?",
      "options": ["Forest trails", "Hills", "Mountains", "Coastal routes", "Desert terrain"]
    },
    {
      "question": "How long will this trek be?",
      "options": ["Day hike", "2-3 days", "4-7 days", "Week+"]
    },
    {
      "question": "What season are you planning for?",
      "options": ["Summer", "Monsoon", "Winter", "Year-round use"]
    }
  ]
}
"""

SYSTEM_PROMPT_ROUND2 = """\
You are a product recommendation assistant generating targeted follow-up questions.

The user has answered 3 initial questions. Based on their answers, generate \
EXACTLY 2 more targeted questions to fill remaining context gaps.

────────────────────────────────────────────
OUTPUT FORMAT  (return ONLY valid JSON, zero markdown)
────────────────────────────────────────────
{
  "questions": [
    {
      "question": "Your question text here",
      "options": ["Option 1", "Option 2", "Option 3"]
    }
  ]
}

────────────────────────────────────────────
RULES
────────────────────────────────────────────
1. Return EXACTLY 2 questions — no more, no less.
2. Questions must be informed by the user's previous answers.
3. Do not repeat or rephrase any already-asked question.
4. Target the highest-value remaining context gaps.
5. Provide 3-6 selectable options per question wherever helpful.
6. These are the FINAL questions — make them count.
7. Budget/price range and specific preferences are good Round 2 topics.
"""

SYSTEM_PROMPT_PRECLARITY = """\
You are a product recommendation assistant. The user's query is vague or \
ambiguous. Ask exactly 1 focused clarifying question to understand their \
basic intent before proceeding to detailed follow-up questions.

────────────────────────────────────────────
OUTPUT FORMAT  (return ONLY valid JSON, zero markdown)
────────────────────────────────────────────
{
  "question": "Your clarifying question here",
  "options": ["Option 1", "Option 2", "Option 3"]
}

────────────────────────────────────────────
RULES
────────────────────────────────────────────
1. Return EXACTLY 1 question.
2. The question should resolve the core ambiguity or vagueness.
3. Provide 2-5 concrete options to help the user articulate their intent.
4. Keep it conversational, not robotic.
"""


def build_round1_messages(
    *,
    query: str,
    domain_context: str | None = None,
) -> list[dict[str, str]]:
    """Build messages to generate Round 1 (3 questions with options)."""
    user_content = f"User query: \"{query}\""
    if domain_context:
        user_content += f"\nDomain context: {domain_context}"
    user_content += "\n\nGenerate exactly 3 follow-up questions with selectable options."

    return [
        {"role": "system", "content": SYSTEM_PROMPT_ROUND1},
        {"role": "user", "content": user_content},
    ]


def build_round2_messages(
    *,
    query: str,
    round1_qa_pairs: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Build messages to generate Round 2 (2 questions with options)."""
    qa_text = "\n".join(
        f"Q: {pair['question']}\nA: {pair['answer']}"
        for pair in round1_qa_pairs
    )

    user_content = (
        f"Original query: \"{query}\"\n\n"
        f"Round 1 Q&A:\n{qa_text}\n\n"
        "Based on these answers, generate exactly 2 more targeted questions "
        "to fill remaining context gaps."
    )

    return [
        {"role": "system", "content": SYSTEM_PROMPT_ROUND2},
        {"role": "user", "content": user_content},
    ]


def build_preclarification_messages(
    *,
    query: str,
    classification: str,
) -> list[dict[str, str]]:
    """Build messages for pre-clarification (Step 2.5) when query is vague/ambiguous."""
    user_content = (
        f"User query: \"{query}\"\n"
        f"Classification: {classification}\n\n"
        "Ask exactly 1 focused clarifying question with selectable options."
    )

    return [
        {"role": "system", "content": SYSTEM_PROMPT_PRECLARITY},
        {"role": "user", "content": user_content},
    ]
