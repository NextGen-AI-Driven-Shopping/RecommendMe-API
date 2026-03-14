"""Health check route handler for `GET /v1/health`."""

from fastapi import APIRouter

from app.core.config import get_settings
from app.models.responses import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Return system health status.

    Probes whether each external service is configured.  Full liveness
    checks (actual HTTP pings) should be added here before production.
    """
    settings = get_settings()

    # Shallow configuration check — does NOT make network requests.
    # Replace each block with a real probe once services are live.
    openai_status = "configured" if settings.OPENAI_API_KEY else "not configured"
    gemini_status = "configured" if settings.GEMINI_API_KEY else "not configured"
    groq_status = "configured" if settings.GROQ_API_KEY else "not configured"
    serpapi_status = "configured" if settings.SERPAPI_KEY else "not configured"

    # TODO: replace with a quick httpx GET to OLLAMA_URL/api/tags
    ollama_status = "configured" if settings.OLLAMA_URL else "not configured"

    # TODO: replace with a real redis-client ping
    redis_status = "configured" if settings.REDIS_URL else "not configured"

    response = HealthResponse(
        status="ok",
        openai=openai_status,
        gemini=gemini_status,
        groq=groq_status,
        serpapi=serpapi_status,
        ollama=ollama_status,
        redis=redis_status,
    )

    return response
