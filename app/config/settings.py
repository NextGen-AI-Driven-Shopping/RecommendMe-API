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
    OPENAI_MODELS: List[str] = []

    GEMINI_API_KEY: str = Field(default="")
    GEMINI_MODEL: str = "gemini-2.0-flash"
    GEMINI_MODELS: List[str] = []
    GROQ_API_KEY: str = Field(default="")
    GROQ_MODEL: str = "gpt-oss-120B"
    GROQ_MODELS: List[str] = []

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
    USERS_CSV_PATH: str = Field(default="app/data/users.csv")

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

    @field_validator("OPENAI_MODELS", "GEMINI_MODELS", "GROQ_MODELS", mode="before")
    @classmethod
    def validate_model_lists(cls, value: Any) -> List[str]:
        if isinstance(value, list):
            return [str(model).strip() for model in value if str(model).strip()]
        if isinstance(value, str):
            if not value.strip():
                return []
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return [str(model).strip() for model in parsed if str(model).strip()]
            except (json.JSONDecodeError, ValueError):
                pass
            return [item.strip() for item in value.split(",") if item.strip()]
        return []

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
