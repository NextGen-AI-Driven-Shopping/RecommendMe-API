"""
Round-based follow-up question engine (Step 3 of Flow.md).

Generates follow-up questions in fixed rounds:
  Round 0: Pre-clarification (1 question) — when query is vague/ambiguous
  Round 1: 3 questions with selectable options
  Round 2: 2 targeted questions based on Round 1 answers

Always exactly 5 total questions across both rounds.
"""

from __future__ import annotations

import json
from typing import Any

from app.core.logger import get_logger
from app.models.internal import ClarificationRoundResult, QuestionWithOptions
from app.prompts.clarification_decision import (
    build_preclarification_messages,
    build_round1_messages,
    build_round2_messages,
)
from app.services.vagueness import _try_provider_chain
from app.utils.prompt_utils import extract_json_payload

logger = get_logger(__name__)


class QuestionEngineError(Exception):
    """Raised when the question engine cannot generate questions."""


async def generate_preclarification_question(
    *,
    query: str,
    classification: str,
) -> QuestionWithOptions:
    """
    Generate a pre-clarification question when query is vague/ambiguous (Step 2.5).

    Returns exactly 1 question with options.
    """
    messages = build_preclarification_messages(query=query, classification=classification)

    raw = await _try_provider_chain(messages, step_name="preclarification")
    if not raw:
        raise QuestionEngineError("All AI providers failed to generate pre-clarification question.")

    try:
        payload = extract_json_payload(raw)
    except (ValueError, json.JSONDecodeError) as exc:
        logger.error("Pre-clarification JSON parse error: %s | raw=%s", exc, raw[:300])
        raise QuestionEngineError("Failed to parse pre-clarification response.") from exc

    question_text = payload.get("question", "").strip()
    options = payload.get("options", [])

    if not question_text:
        raise QuestionEngineError("AI returned empty pre-clarification question.")

    return QuestionWithOptions(
        question=question_text,
        options=[str(opt).strip() for opt in options if str(opt).strip()],
    )


async def generate_round1_questions(
    *,
    query: str,
    domain_context: str | None = None,
) -> ClarificationRoundResult:
    """
    Generate Round 1 follow-up questions (exactly 3 with options).

    Args:
        query: The user's original query.
        domain_context: Optional detected domain context.

    Returns:
        ClarificationRoundResult with exactly 3 questions.
    """
    messages = build_round1_messages(query=query, domain_context=domain_context)

    raw = await _try_provider_chain(messages, step_name="round1_questions")
    if not raw:
        raise QuestionEngineError("All AI providers failed to generate Round 1 questions.")

    try:
        payload = extract_json_payload(raw)
    except (ValueError, json.JSONDecodeError) as exc:
        logger.error("Round 1 JSON parse error: %s | raw=%s", exc, raw[:300])
        raise QuestionEngineError("Failed to parse Round 1 questions.") from exc

    raw_questions = payload.get("questions", [])
    if not isinstance(raw_questions, list) or len(raw_questions) < 1:
        raise QuestionEngineError("AI returned no Round 1 questions.")

    questions: list[QuestionWithOptions] = []
    for item in raw_questions[:3]:
        if isinstance(item, dict):
            q_text = str(item.get("question", "")).strip()
            q_options = [str(o).strip() for o in item.get("options", []) if str(o).strip()]
        elif isinstance(item, str):
            q_text = item.strip()
            q_options = []
        else:
            continue

        if q_text:
            questions.append(QuestionWithOptions(question=q_text, options=q_options))

    if not questions:
        raise QuestionEngineError("AI returned no valid Round 1 questions.")

    # Pad to 3 if AI returned fewer (should rarely happen)
    while len(questions) < 3:
        questions.append(QuestionWithOptions(
            question=f"Tell us more about what you need #{len(questions) + 1}?",
            options=[],
        ))

    return ClarificationRoundResult(
        round_number=1,
        questions=questions[:3],
        provider="multi-provider-chain",
    )


async def generate_round2_questions(
    *,
    query: str,
    round1_qa_pairs: list[dict[str, str]],
) -> ClarificationRoundResult:
    """
    Generate Round 2 follow-up questions (exactly 2, informed by Round 1 answers).

    Args:
        query: The user's original query.
        round1_qa_pairs: List of {"question": ..., "answer": ...} from Round 1.

    Returns:
        ClarificationRoundResult with exactly 2 questions.
    """
    messages = build_round2_messages(query=query, round1_qa_pairs=round1_qa_pairs)

    raw = await _try_provider_chain(messages, step_name="round2_questions")
    if not raw:
        raise QuestionEngineError("All AI providers failed to generate Round 2 questions.")

    try:
        payload = extract_json_payload(raw)
    except (ValueError, json.JSONDecodeError) as exc:
        logger.error("Round 2 JSON parse error: %s | raw=%s", exc, raw[:300])
        raise QuestionEngineError("Failed to parse Round 2 questions.") from exc

    raw_questions = payload.get("questions", [])
    if not isinstance(raw_questions, list) or len(raw_questions) < 1:
        raise QuestionEngineError("AI returned no Round 2 questions.")

    questions: list[QuestionWithOptions] = []
    for item in raw_questions[:2]:
        if isinstance(item, dict):
            q_text = str(item.get("question", "")).strip()
            q_options = [str(o).strip() for o in item.get("options", []) if str(o).strip()]
        elif isinstance(item, str):
            q_text = item.strip()
            q_options = []
        else:
            continue

        if q_text:
            questions.append(QuestionWithOptions(question=q_text, options=q_options))

    if not questions:
        raise QuestionEngineError("AI returned no valid Round 2 questions.")

    # Pad to 2 if AI returned fewer
    while len(questions) < 2:
        questions.append(QuestionWithOptions(
            question=f"Any other preferences or requirements?",
            options=[],
        ))

    return ClarificationRoundResult(
        round_number=2,
        questions=questions[:2],
        provider="multi-provider-chain",
    )
