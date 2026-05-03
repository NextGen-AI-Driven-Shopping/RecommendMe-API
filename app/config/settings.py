"""Application settings.

All configuration is loaded from environment variables and optional .env files.
Call get_settings() to obtain the singleton Settings instance anywhere in
the application.
"""

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, List

import yaml
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings.sources import DotEnvSettingsSource, PydanticBaseSettingsSource


_LIST_FIELD_NAMES = {
    "OPENAI_MODELS",
    "GEMINI_MODELS",
    "GROQ_MODELS",
    "OLLAMA_MODELS",
    "CORS_ORIGINS",
}


def _parse_lenient_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]

    if not isinstance(value, str):
        return []

    cleaned = value.strip()
    if not cleaned:
        return []

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    except (json.JSONDecodeError, ValueError):
        pass

    trimmed = cleaned.strip("[]")
    parts = [segment.strip().strip('"').strip("'") for segment in re.split(r"[,\n]", trimmed)]
    return [segment for segment in parts if segment]


def _normalize_model_list(value: Any) -> list[str]:
    if isinstance(value, dict):
        for key in ("models", "model", "values"):
            if key in value:
                return _parse_lenient_list(value[key])
        return []

    return _parse_lenient_list(value)


def _load_provider_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}

    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    if not isinstance(raw, dict):
        return {}

    providers = raw.get("providers")
    if isinstance(providers, dict):
        return providers
    return raw


class LenientDotEnvSettingsSource(DotEnvSettingsSource):
    def prepare_field_value(self, field_name, field, value, value_is_complex):
        if field_name in _LIST_FIELD_NAMES:
            if value is None:
                return None
            parsed = _parse_lenient_list(value)
            return parsed or None
        return super().prepare_field_value(field_name, field, value, value_is_complex)


class Settings(BaseSettings):
    APP_NAME: str = "RecommendMe API"
    APP_ENV: str = "development"
    DEBUG: bool = False

    OPENAI_API_KEY: str = Field(default="")
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_MODELS: List[str] = ["gpt-4.1", "gpt-4o", "gpt-4.1-mini"]

    GEMINI_API_KEY: str = Field(default="")
    GEMINI_MODEL: str = "gemini-2.0-flash"
    GEMINI_MODELS: List[str] = ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash"]
    GROQ_API_KEY: str = Field(default="")
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_MODELS: List[str] = ["gpt-oss-120b", "llama-3.3-70b-versatile", "qwen/qwen3-32b"]

    GROK_API_KEY: str = Field(default="")
    OTHER_API_KEY: str = Field(default="")

    OLLAMA_URL: str = Field(default="http://localhost:11434")
    OLLAMA_MODEL: str = "phi3"
    OLLAMA_MODELS: List[str] = ["phi3", "phi3:latest", "llama3.2"]

    AI_PROVIDER_CONFIG_PATH: str = Field(default="app/config/provider_models.yml")

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
    AUTH_TOKEN_SECRET: str = Field(default="recommendme-dev-secret-change-me")
    AUTH_TOKEN_TTL_MINUTES: int = 10080
    ALLOW_DEV_LOGIN_BYPASS: bool = False
    REDIS_URL: str = Field(default="")

    SUPABASE_URL: str = Field(default="")
    SUPABASE_JWT_SECRET: str = Field(default="")
    SUPABASE_JWKS_URL: str = Field(default="")

    AFFILIATE_TAG: str = Field(default="")
    USERS_CSV_PATH: str = Field(default="app/data/users.csv")
    PROFILE_STORE_PATH: str = Field(default="app/data/profiles.json")
    PROFILE_UPLOAD_DIR: str = Field(default="app/data/uploads/avatars")

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def validate_cors_origins(cls, v: Any) -> List[str]:
        parsed = _parse_lenient_list(v)
        if parsed:
            return parsed
        return [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8080",
            "http://127.0.0.1:8080",
        ]

    @field_validator("OPENAI_MODELS", "GEMINI_MODELS", "GROQ_MODELS", "OLLAMA_MODELS", mode="before")
    @classmethod
    def validate_model_lists(cls, value: Any) -> List[str]:
        return _parse_lenient_list(value)

    @model_validator(mode="before")
    @classmethod
    def load_provider_model_defaults(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values

        config_path_value = values.get("AI_PROVIDER_CONFIG_PATH") or "app/config/provider_models.yml"
        config_path = Path(str(config_path_value))
        if not config_path.is_absolute():
            config_path = Path(__file__).resolve().parents[2] / config_path

        provider_config = _load_provider_config(config_path)

        provider_sources = {
            "GROQ_MODELS": provider_config.get("groq"),
            "OPENAI_MODELS": provider_config.get("openai"),
            "GEMINI_MODELS": provider_config.get("gemini"),
            "OLLAMA_MODELS": provider_config.get("ollama"),
        }

        for field_name, source in provider_sources.items():
            if values.get(field_name):
                continue
            models = _normalize_model_list(source)
            if models:
                values[field_name] = models

        if not values.get("GROQ_MODEL") and values.get("GROQ_MODELS"):
            groq_models = _normalize_model_list(values.get("GROQ_MODELS"))
            if groq_models:
                values["GROQ_MODEL"] = groq_models[0]

        if not values.get("OPENAI_MODEL") and values.get("OPENAI_MODELS"):
            openai_models = _normalize_model_list(values.get("OPENAI_MODELS"))
            if openai_models:
                values["OPENAI_MODEL"] = openai_models[0]

        if not values.get("GEMINI_MODEL") and values.get("GEMINI_MODELS"):
            gemini_models = _normalize_model_list(values.get("GEMINI_MODELS"))
            if gemini_models:
                values["GEMINI_MODEL"] = gemini_models[0]

        if not values.get("OLLAMA_MODEL") and values.get("OLLAMA_MODELS"):
            ollama_models = _normalize_model_list(values.get("OLLAMA_MODELS"))
            if ollama_models:
                values["OLLAMA_MODEL"] = ollama_models[0]

        return values

    @model_validator(mode="after")
    def enforce_security_constraints(self):
        if self.APP_ENV.lower() == "production":
            if not self.AUTH_TOKEN_SECRET or self.AUTH_TOKEN_SECRET == "recommendme-dev-secret-change-me":
                raise ValueError("AUTH_TOKEN_SECRET must be explicitly set to a non-default value in production")
        return self

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        return (
            init_settings,
            env_settings,
            LenientDotEnvSettingsSource(settings_cls),
            file_secret_settings,
        )

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
