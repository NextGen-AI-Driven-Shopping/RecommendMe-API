from pydantic import Field, AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    # 1. App Configuration
    APP_NAME: str = "RecommendMe API"
    APP_ENV: str = "development"
    DEBUG: bool = False

    # 2. AI Service Configurations
    OPENAI_API_KEY: str
    OLLAMA_URL: str = "http://localhost:11434/api/generate"
    OLLAMA_MODEL: str = "phi3"

    # 3. External API Keys
    SERPAPI_KEY: str = Field(default="")

    # 4. Infrastructure & Security
    # Whitelisted origins for CORS (the frontend URLs)
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]
    
    # Global Rate Limit (Requirement: 10 requests/minute)
    RATE_LIMIT_PER_MINUTE: int = 10
    SESSION_TTL_MINUTES: int = 30

    # This tells Pydantic to read from the .env file
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore"  # Ignore extra variables in .env that aren't defined here
    )

# Create a single instance to be used across the app
settings = Settings()