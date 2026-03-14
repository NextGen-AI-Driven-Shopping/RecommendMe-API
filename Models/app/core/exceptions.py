"""
Custom exception classes for the RecommendMe API.

Each exception maps to a specific HTTP status code and error code
used in the standardized ErrorResponse envelope.
"""

from __future__ import annotations


class RecommendMeError(Exception):
    """Base exception for all RecommendMe application errors."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        retry_after: int | None = None,
    ) -> None:
        self.message = message
        self.code = code
        self.status_code = status_code
        self.retry_after = retry_after
        super().__init__(message)


# ---------------------------------------------------------------------------
# Validation errors (HTTP 400)
# ---------------------------------------------------------------------------

class QueryTooShortError(RecommendMeError):
    """Raised when the user query has fewer words than the minimum."""

    def __init__(self, min_words: int = 3) -> None:
        super().__init__(
            message=f"Your query is too short. Please use at least {min_words} words.",
            code="QUERY_TOO_SHORT",
            status_code=400,
        )


class QueryTooLongError(RecommendMeError):
    """Raised when the user query exceeds the maximum word count."""

    def __init__(self, max_words: int = 500) -> None:
        super().__init__(
            message=f"Your query is too long. Please keep it under {max_words} words.",
            code="QUERY_TOO_LONG",
            status_code=400,
        )


class InjectionDetectedError(RecommendMeError):
    """Raised when a prompt-injection pattern is detected in user input."""

    def __init__(self) -> None:
        super().__init__(
            message="Your message contains disallowed patterns. Please rephrase.",
            code="INJECTION_DETECTED",
            status_code=400,
        )


# ---------------------------------------------------------------------------
# Session errors
# ---------------------------------------------------------------------------

class SessionExpiredError(RecommendMeError):
    """Raised when the referenced session has expired due to inactivity."""

    def __init__(self, ttl_minutes: int = 30) -> None:
        super().__init__(
            message=f"Your session has expired after {ttl_minutes} minutes of inactivity. Please start a new conversation.",
            code="SESSION_EXPIRED",
            status_code=401,
        )


class SessionNotFoundError(RecommendMeError):
    """Raised when the referenced session_id does not exist."""

    def __init__(self) -> None:
        super().__init__(
            message="Session not found. Please start a new conversation.",
            code="SESSION_NOT_FOUND",
            status_code=404,
        )


# ---------------------------------------------------------------------------
# External-service errors
# ---------------------------------------------------------------------------

class OllamaUnavailableError(RecommendMeError):
    """Raised when Ollama is unreachable (triggers silent fallback)."""

    def __init__(self) -> None:
        super().__init__(
            message="Local AI model is unavailable. Falling back to cloud model.",
            code="OLLAMA_UNAVAILABLE",
            status_code=503,
        )


class OpenAIRateLimitError(RecommendMeError):
    """Raised when OpenAI returns HTTP 429."""

    def __init__(self, retry_after: int = 5) -> None:
        super().__init__(
            message="Our AI is momentarily busy. Please try again in a few seconds.",
            code="OPENAI_RATE_LIMIT",
            status_code=429,
            retry_after=retry_after,
        )


class SerpAPINoResultsError(RecommendMeError):
    """Raised when SerpAPI returns an empty result set."""

    def __init__(self, category: str = "") -> None:
        detail = f" for '{category}'" if category else ""
        super().__init__(
            message=f"No products found{detail}. Try broadening your search.",
            code="SERP_NO_RESULTS",
            status_code=200,  # Not a hard failure — partial results are acceptable
        )


class SerpAPIQuotaExceededError(RecommendMeError):
    """Raised when the SerpAPI monthly quota is exhausted."""

    def __init__(self) -> None:
        super().__init__(
            message="Product search is temporarily unavailable. Please try again later.",
            code="SERP_QUOTA_EXCEEDED",
            status_code=503,
        )
