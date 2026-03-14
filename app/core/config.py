"""
Application settings.

All configuration is loaded from environment variables or the .env file.
Call get_settings() to obtain the singleton Settings instance anywhere in
the application.  Do NOT import the module-level `settings` object directly
from new code — prefer get_settings() so the dependency can be overridden
in tests.
"""

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ------------------------------------------------------------------ #
    # 1. Application metadata
    # ------------------------------------------------------------------ #
    APP_NAME: str = "RecommendMe API"
    APP_ENV: str = "development"
    DEBUG: bool = False

    # ------------------------------------------------------------------ #
    # 2. AI service configuration
    # ------------------------------------------------------------------ #
    # OpenAI API key — required in production, optional during development.
    OPENAI_API_KEY: str = Field(default="")
    OPENAI_MODEL: str = "gpt-4o"

    # Gemini and GROQ keys for multi-provider category reasoning fallback.
    GEMINI_API_KEY: str = Field(default="")
    GEMINI_MODEL: str = "gemini-1.5-flash"
    GROQ_API_KEY: str = Field(default="")
    GROQ_MODEL: str = "llama-3.1-70b-versatile"

    # Ollama local model endpoint and model name.
    # The base URL should point to the /api root (without a trailing path).
    OLLAMA_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "phi3"

    # ------------------------------------------------------------------ #
    # 3. External API keys
    # ------------------------------------------------------------------ #
    # SerpAPI key for Google Shopping product search.
    SERPAPI_KEY: str = Field(default="")

    # ------------------------------------------------------------------ #
    # 4. Infrastructure & security
    # ------------------------------------------------------------------ #
    # Comma-separated list of allowed frontend origins for CORS.
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # Global per-IP rate limit enforced by the rate-limiter dependency.
    RATE_LIMIT_PER_MINUTE: int = 10

    # In-memory session TTL (minutes).  Redis TTL is derived from this value.
    SESSION_TTL_MINUTES: int = 30

    # Redis connection URL for the optional caching layer.
    REDIS_URL: str = "redis://localhost:6379"

    # ------------------------------------------------------------------ #
    # 5. Optional monetisation
    # ------------------------------------------------------------------ #
    # Affiliate tag appended to product URLs (leave empty to disable).
    AFFILIATE_TAG: str = Field(default="")

    # ------------------------------------------------------------------ #
    # Pydantic settings configuration
    # ------------------------------------------------------------------ #
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # Silently ignore extra variables that appear in the .env file but
        # are not declared as fields above (e.g. developer personal vars).
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings singleton.

    Using lru_cache means the .env file is only parsed once per process,
    which avoids redundant I/O and makes the instance straightforward to
    mock in tests via dependency injection or monkeypatching.
    """
    return Settings()


# Convenience module-level instance kept for backward-compatibility with
# existing imports that reference `settings` directly.  New code should
# call get_settings() instead.
settings = get_settings()