"""
Input validation utilities.

Validates user-submitted query strings for:
  - Length bounds (min / max character count).
  - Prompt injection patterns (role overrides, jailbreak attempts).
  - HTML and SQL injection markers.

All checks are case-insensitive and run before any AI call is made.
"""

import re

MAX_QUERY_LENGTH: int = 500
MIN_QUERY_LENGTH: int = 3

# Patterns that indicate attempted injection or abuse
_INJECTION_PATTERNS: list[str] = [
    r"ignore\s+(previous|all)\s+instructions",
    r"you\s+are\s+now\s+",
    r"\bact\s+as\b",
    r"\bdan\b",                       # "Do Anything Now" jailbreak keyword
    r"<\s*script.*?>",                # HTML script tag
    r";\s*drop\s+table",              # SQL injection
    r"--\s*$",                        # SQL comment termination
]

_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in _INJECTION_PATTERNS]


def validate_query_length(query: str) -> bool:
    """Return True if the query length is within acceptable bounds."""
    return MIN_QUERY_LENGTH <= len(query) <= MAX_QUERY_LENGTH


def detect_injection(query: str) -> bool:
    """
    Return True if the query matches any known injection pattern.

    Checks for prompt injection, HTML injection, and SQL injection markers.
    """
    return any(pattern.search(query) for pattern in _COMPILED_PATTERNS)


def is_valid_query(query: str) -> tuple[bool, str]:
    """
    Run all validations on a query string.

    Returns:
        (True, "")             if the query passes all checks.
        (False, reason_str)    if the query fails any check.
    """
    if not validate_query_length(query):
        return False, (
            f"Query must be between {MIN_QUERY_LENGTH} and "
            f"{MAX_QUERY_LENGTH} characters."
        )
    if detect_injection(query):
        return False, "Query contains disallowed patterns."
    return True, ""
