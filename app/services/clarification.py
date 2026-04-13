"""Clarification planning and sufficiency scoring for staged follow-up flow."""

from __future__ import annotations

from typing import Any

from app.services.dynamic_intent_analyzer import (
    DynamicFollowUpGenerator,
    DynamicIntentAnalyzer,
)


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _extract_pairs(clarification: list[Any] | None) -> list[tuple[str, str]]:
    if not clarification:
        return []

    pairs: list[tuple[str, str]] = []
    for item in clarification:
        if isinstance(item, dict):
            question = _as_text(item.get("question"))
            answer = _as_text(item.get("answer"))
        else:
            question = _as_text(getattr(item, "question", ""))
            answer = _as_text(getattr(item, "answer", ""))
        if question and answer:
            pairs.append((question, answer))
    return pairs


def _coverage_score(signals: dict) -> float:
    # Weighted for recommendation relevance: use-case/type/price are strongest.
    total_weight = 0.0
    achieved = 0.0
    weighted_keys = [
        ("has_use_case", 0.25),
        ("has_type", 0.20),
        ("has_price", 0.20),
        ("has_environment", 0.15),
        ("has_timeframe", 0.10),
    ]
    for key, weight in weighted_keys:
        total_weight += weight
        if signals.get(key):
            achieved += weight

    # Product noun presence is mandatory context for shopping.
    total_weight += 0.10
    if signals.get("primary_nouns"):
        achieved += 0.10

    return achieved / total_weight if total_weight else 0.0


class ClarificationPlanner:
    """Generates staged questions and evaluates if user input is sufficient."""

    def __init__(self) -> None:
        self._analyzer = DynamicIntentAnalyzer()
        self._generator = DynamicFollowUpGenerator()

    def generate_initial_questions(self, query: str, max_questions: int = 1) -> list[str]:
        signals = self._analyzer.extract_domain_signals(query)
        missing = self._analyzer.determine_missing_info(signals)
        return self._generator.generate_from_signals(
            query=query,
            signals=signals,
            missing=missing,
            max_questions=max_questions,
        )

    def validate_sufficiency(
        self,
        query: str,
        clarification: list[Any] | None,
        *,
        threshold: float = 0.68,
        min_answers_before_pass: int = 3,
    ) -> tuple[bool, float, dict[str, bool]]:
        pairs = _extract_pairs(clarification)
        combined = " ".join([query] + [answer for _, answer in pairs]).strip()
        signals = self._analyzer.extract_domain_signals(combined)
        missing = self._analyzer.determine_missing_info(signals)

        score = _coverage_score(signals)
        sufficient_by_score = score >= threshold

        # Stop clarification once the core shopping context is known.
        has_core_context = bool(signals.get("primary_nouns")) and bool(signals.get("has_use_case")) and bool(signals.get("has_price"))
        has_decision_context = bool(signals.get("has_type")) or bool(signals.get("has_environment")) or len(pairs) >= 2

        # Require at least min answers unless score is very high or core context is complete.
        answers_count = len(pairs)
        sufficient = (
            (answers_count >= min_answers_before_pass and sufficient_by_score)
            or (has_core_context and has_decision_context)
            or score >= 0.85
        )
        return sufficient, round(score, 3), missing

    def generate_additional_questions(
        self,
        query: str,
        clarification: list[Any] | None,
        *,
        max_additional: int = 1,
    ) -> list[str]:
        pairs = _extract_pairs(clarification)
        asked_questions = {q for q, _ in pairs}
        combined = " ".join([query] + [answer for _, answer in pairs]).strip()

        signals = self._analyzer.extract_domain_signals(combined)
        missing = self._analyzer.determine_missing_info(signals)
        candidates = self._generator.generate_from_signals(
            query=combined,
            signals=signals,
            missing=missing,
            max_questions=5,
        )

        additional: list[str] = []
        for question in candidates:
            if question in asked_questions:
                continue
            additional.append(question)
            if len(additional) >= max_additional:
                break
        return additional

    def plan_next_step(
        self,
        query: str,
        clarification: list[Any] | None,
        *,
        max_total_questions: int = 5,
    ) -> dict[str, Any]:
        pairs = _extract_pairs(clarification)
        asked_count = len(pairs)

        if asked_count == 0:
            initial = self.generate_initial_questions(query, max_questions=1)
            return {
                "sufficient": False,
                "sufficiency_score": 0.0,
                "round": 1,
                "asked_questions": 0,
                "next_questions": initial,
            }

        sufficient, score, _missing = self.validate_sufficiency(query, clarification)
        if sufficient or asked_count >= max_total_questions:
            return {
                "sufficient": True,
                "sufficiency_score": score,
                "round": 2 if asked_count > 3 else 1,
                "asked_questions": asked_count,
                "next_questions": [],
            }

        remaining = max(0, max_total_questions - asked_count)
        if remaining > 0:
            additional = self.generate_additional_questions(
                query,
                clarification,
                max_additional=1,
            )
            return {
                "sufficient": False,
                "sufficiency_score": score,
                "round": 2 if asked_count >= 3 else 1,
                "asked_questions": asked_count,
                "next_questions": additional,
            }

        return {
            "sufficient": False,
            "sufficiency_score": score,
            "round": 1,
            "asked_questions": asked_count,
            "next_questions": [],
        }
