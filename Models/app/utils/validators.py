"""
Input validation utilities for the RecommendMe API.

Standalone functions used by route handlers and services to validate
and sanitize user input *before* it reaches any AI model.
"""

from __future__ import annotations

import re
from uuid import UUID

from app.core.exceptions import (
    InjectionDetectedError,
    QueryTooLongError,
    QueryTooShortError,
)


# ---------------------------------------------------------------------------
# Prompt-injection patterns (case-insensitive)
# ---------------------------------------------------------------------------

_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    # Direct instruction overrides
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?|rules?)", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous|prior|above)\s+(instructions?|context)", re.IGNORECASE),
    re.compile(r"forget\s+(everything|all)\s+(above|before|previously)", re.IGNORECASE),

    # Role-play / persona hijacking
    re.compile(r"you\s+are\s+now\s+(a|an|the)\s+", re.IGNORECASE),
    re.compile(r"act\s+as\s+(if\s+you\s+are|a|an)\s+", re.IGNORECASE),
    re.compile(r"pretend\s+(you\s+are|to\s+be)\s+", re.IGNORECASE),

    # System-prompt leaking
    re.compile(r"(reveal|show|print|output|display)\s+(your\s+)?(system\s+prompt|instructions|rules)", re.IGNORECASE),
    re.compile(r"what\s+(are|is)\s+your\s+(system\s+)?prompt", re.IGNORECASE),

    # Delimiter / role injection
    re.compile(r"\bsystem\s*:", re.IGNORECASE),
    re.compile(r"\bassistant\s*:", re.IGNORECASE),
    re.compile(r"<\|?(system|im_start|endoftext)\|?>", re.IGNORECASE),

    # Encoded bypass attempts
    re.compile(r"(base64|rot13|hex)\s*(encode|decode)", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Control character pattern
# ---------------------------------------------------------------------------

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_EXCESSIVE_WHITESPACE = re.compile(r"[ \t]+")
_EXCESSIVE_NEWLINES = re.compile(r"\n{3,}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_query_length(
    text: str,
    min_words: int = 3,
    max_words: int = 500,
) -> str:
    """
    Validate that ``text`` has between ``min_words`` and ``max_words`` words.

    Parameters
    ----------
    text : str
        The raw query string.
    min_words : int
        Minimum word count (inclusive). Default: 3.
    max_words : int
        Maximum word count (inclusive). Default: 500.

    Returns
    -------
    str
        The original text, unchanged.

    Raises
    ------
    QueryTooShortError
        If the word count is below ``min_words``.
    QueryTooLongError
        If the word count exceeds ``max_words``.
    """
    word_count = len(text.split())
    if word_count < min_words:
        raise QueryTooShortError(min_words)
    if word_count > max_words:
        raise QueryTooLongError(max_words)
    return text


def sanitize_input(text: str) -> str:
    """
    Clean user input for safe downstream processing.

    Steps:
      1. Strip leading / trailing whitespace.
      2. Remove ASCII control characters (except ``\\n``, ``\\r``, ``\\t``).
      3. Collapse consecutive spaces/tabs into a single space.
      4. Collapse 3+ consecutive newlines into 2.

    Parameters
    ----------
    text : str
        Raw user text.

    Returns
    -------
    str
        Sanitized text.
    """
    text = text.strip()
    text = _CONTROL_CHARS.sub("", text)
    # Collapse horizontal whitespace (not newlines)
    text = _EXCESSIVE_WHITESPACE.sub(" ", text)
    # Collapse vertical whitespace
    text = _EXCESSIVE_NEWLINES.sub("\n\n", text)
    return text


def detect_injection(text: str) -> bool:
    """
    Check whether ``text`` contains any known prompt-injection patterns.

    Parameters
    ----------
    text : str
        The user message to scan.

    Returns
    -------
    bool
        ``True`` if an injection pattern was found.
    """
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            return True
    return False


def validate_and_sanitize(
    text: str,
    min_words: int = 3,
    max_words: int = 500,
) -> str:
    """
    Full input validation pipeline: sanitize → length check → injection scan.

    Parameters
    ----------
    text : str
        Raw user message.
    min_words : int
        Minimum word count after sanitization.
    max_words : int
        Maximum word count after sanitization.

    Returns
    -------
    str
        Clean, validated text ready for AI processing.

    Raises
    ------
    QueryTooShortError
        If text is too short after sanitization.
    QueryTooLongError
        If text exceeds the word limit.
    InjectionDetectedError
        If a prompt-injection pattern is detected.
    """
    text = sanitize_input(text)
    validate_query_length(text, min_words, max_words)
    if detect_injection(text):
        raise InjectionDetectedError()
    return text


def validate_session_id(raw_id: str) -> UUID:
    """
    Validate that ``raw_id`` is a well-formed UUID.

    Parameters
    ----------
    raw_id : str
        The session_id string from the client.

    Returns
    -------
    UUID
        Parsed UUID object.

    Raises
    ------
    ValueError
        If the string is not a valid UUID.
    """
    try:
        return UUID(raw_id)
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"Invalid session_id: '{raw_id}' is not a valid UUID.") from exc
