"""
Application configuration.

All settings are loaded from environment variables (or a .env file)
via Pydantic BaseSettings.  Add new configuration values here; never
hard-code secrets anywhere else in the codebase.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed settings container populated from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "RecommendMe API"
    debug: bool = False
    log_level: str = "INFO"

    # OpenAI
    openai_api_key: str = ""
    openai_model_primary: str = "gpt-4o"
    openai_model_fallback: str = "gpt-4o-mini"

    # Ollama (local AI fallback)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"

    # SerpAPI
    serpapi_api_key: str = ""

    # Redis
    redis_url: str = "redis://localhost:6379"
    cache_ttl_seconds: int = 3600

    # Affiliate
    affiliate_tag: str = ""

    # Rate limiting
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()
