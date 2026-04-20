"""Legacy-compatible intent utilities without static question templates.

Question generation is intentionally delegated to runtime AI decision services.
"""

from __future__ import annotations

import re
from typing import Any

from app.core.logger import get_logger

logger = get_logger(__name__)


class DynamicIntentAnalyzer:
    """Extract lightweight semantic signals from raw text."""

    @staticmethod
    def extract_domain_signals(query: str) -> dict[str, Any]:
        text = (query or "").strip().lower()
        tokens = re.findall(r"[a-z0-9]+", text)

        has_numeric_constraint = bool(re.search(r"\d", text))
        has_comparison_intent = bool(re.search(r"\b(best|better|vs|compare|top|rank)\b", text))
        has_preference_hint = bool(re.search(r"\b(prefer|need|must|want|gift|for|with|without)\b", text))
        has_context_hint = bool(re.search(r"\b(indoor|outdoor|home|office|travel|daily|professional|casual)\b", text))

        return {
            "token_count": len(tokens),
            "has_numeric_constraint": has_numeric_constraint,
            "has_comparison_intent": has_comparison_intent,
            "has_preference_hint": has_preference_hint,
            "has_context_hint": has_context_hint,
            "query": text,
        }

    @staticmethod
    def determine_missing_info(signals: dict[str, Any]) -> dict[str, Any]:
        missing = {
            "constraint": not bool(signals.get("has_numeric_constraint")),
            "preference": not bool(signals.get("has_preference_hint")),
            "context": not bool(signals.get("has_context_hint")),
        }
        missing["count"] = sum(1 for key, value in missing.items() if key != "count" and value)
        return missing

    @staticmethod
    def is_query_clear(signals_or_query, missing: dict[str, Any] | None = None) -> bool:
        if isinstance(signals_or_query, str):
            signals = DynamicIntentAnalyzer.extract_domain_signals(signals_or_query)
            missing = DynamicIntentAnalyzer.determine_missing_info(signals)
        else:
            signals = signals_or_query
            if missing is None:
                missing = DynamicIntentAnalyzer.determine_missing_info(signals)

        token_count = int(signals.get("token_count") or 0)
        missing_count = int((missing or {}).get("count") or 0)

        if token_count < 3:
            return False

        if token_count >= 8 and missing_count <= 1:
            return True

        return missing_count == 0


class DynamicFollowUpGenerator:
    """Legacy compatibility shim.

    No static question templates are used here. Runtime AI services are
    responsible for all follow-up question generation.
    """

    @staticmethod
    def generate_from_signals(
        query: str,
        signals: dict[str, Any],
        missing: dict[str, Any],
        max_questions: int = 3,
    ) -> list[str]:
        logger.info(
            "DynamicFollowUpGenerator invoked without AI runtime engine query=%s missing=%s",
            (query or "")[:120],
            missing,
        )
        return []
