"""Application settings.

All configuration is loaded from environment variables and optional .env files.
Call get_settings() to obtain the singleton Settings instance anywhere in
the application.
"""

import json
from functools import lru_cache
from typing import Any, List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "RecommendMe API"
    APP_ENV: str = "development"
    DEBUG: bool = False

    OPENAI_API_KEY: str = Field(default="")
    OPENAI_MODEL: str = "gpt-4o"

    GEMINI_API_KEY: str = Field(default="")
    GEMINI_MODEL: str = "gemini-2.0-flash"
    GROQ_API_KEY: str = Field(default="")
    GROQ_MODEL: str = "gpt-oss-120B"

    GROK_API_KEY: str = Field(default="")
    OTHER_API_KEY: str = Field(default="")

    OLLAMA_URL: str = Field(default="")
    OLLAMA_MODEL: str = "phi3"

    SERPAPI_KEY: str = Field(default="")

    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ]
    CORS_ORIGIN_REGEX: str = r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$"

    RATE_LIMIT_PER_MINUTE: int = 10
    SESSION_TTL_MINUTES: int = 30
    REDIS_URL: str = Field(default="")
    AFFILIATE_TAG: str = Field(default="")

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def validate_cors_origins(cls, v: Any) -> List[str]:
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except (json.JSONDecodeError, ValueError):
                pass

            if v:
                return [origin.strip() for origin in v.split(",") if origin.strip()]

        return [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8080",
            "http://127.0.0.1:8080",
        ]

    model_config = SettingsConfigDict(
        env_file=("Environment/.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings singleton."""
    try:
        return Settings()
    except Exception as exc:
        import sys

        print(f"ERROR: Failed to load settings: {exc}", file=sys.stderr)
        raise
