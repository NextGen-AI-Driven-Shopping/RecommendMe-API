"""
Application settings.

All configuration is loaded from environment variables or the .env file.
Call get_settings() to obtain the singleton Settings instance anywhere in
the application.  Do NOT import the module-level `settings` object directly
from new code — prefer get_settings() so the dependency can be overridden
in tests.
"""

import json
from functools import lru_cache
from typing import Any, List

from pydantic import Field, field_validator
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
    GEMINI_MODEL: str = "gemini-2.0-flash"
    GROQ_API_KEY: str = Field(default="")
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    
    # Additional AI and third-party APIs
    GROK_API_KEY: str = Field(default="")
    OTHER_API_KEY: str = Field(default="")

    # Ollama local model endpoint and model name.
    # The base URL should point to the /api root (without a trailing path).
    # Set OLLAMA_URL env var to enable; defaults to empty (disabled).
    OLLAMA_URL: str = Field(default="")
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
    # Production MUST set this explicitly via env var or it defaults to localhost.
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ]
    # Optional regex for local development origins (e.g. [::1], custom Vite ports).
    CORS_ORIGIN_REGEX: str = r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$"

    # Global per-IP rate limit enforced by the rate-limiter dependency.
    RATE_LIMIT_PER_MINUTE: int = 10

    # In-memory session TTL (minutes).  Redis TTL is derived from this value.
    SESSION_TTL_MINUTES: int = 30

    # Redis connection URL for optional caching layer.
    # If empty, in-memory cache is used (not recommended for multi-instance).
    REDIS_URL: str = Field(default="")

    # ------------------------------------------------------------------ #
    # 5. Optional monetisation
    # ------------------------------------------------------------------ #
    # Affiliate tag appended to product URLs (leave empty to disable).
    AFFILIATE_TAG: str = Field(default="")

    # ------------------------------------------------------------------ #
    # Validators
    # ------------------------------------------------------------------ #
    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def validate_cors_origins(cls, v: Any) -> List[str]:
        """
        Safely parse CORS_ORIGINS from environment variables.
        
        Handles both JSON array strings and comma-separated strings,
        preserving defaults if parsing fails.
        """
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            # Try to parse as JSON array first
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except (json.JSONDecodeError, ValueError):
                pass
            
            # Fallback: treat as comma-separated string
            if v:
                return [origin.strip() for origin in v.split(",") if origin.strip()]
        
        # Return default if parsing completely fails
        return [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8080",
            "http://127.0.0.1:8080",
        ]

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
    try:
        return Settings()
    except Exception as e:
        import sys
        print(f"ERROR: Failed to load settings: {e}", file=sys.stderr)
        raise


# NOTE: Removed module-level settings = get_settings() call.
# Settings are now lazily initialized on first use via get_settings().
# This prevents import-time errors if environment variables are misconfigured.