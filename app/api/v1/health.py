"""
Health check route handler — GET /v1/health.

Returns the current system status.  Each external dependency is probed
lightly: a missing API key or unreachable service is reported without
crashing the endpoint.
"""

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
    print("\n" + "=" * 60)
    print("[HEALTH ENDPOINT HIT]")

    settings = get_settings()

    # Shallow configuration check — does NOT make network requests.
    # Replace each block with a real probe once services are live.
    openai_status  = "configured" if settings.OPENAI_API_KEY  else "not configured"
    serpapi_status = "configured" if settings.SERPAPI_KEY     else "not configured"

    # TODO: replace with a quick httpx GET to OLLAMA_URL/api/tags
    ollama_status = "configured" if settings.OLLAMA_URL else "not configured"

    # TODO: replace with a real redis-client ping
    redis_status = "configured" if settings.REDIS_URL else "not configured"

    response = HealthResponse(
        status="ok",
        openai=openai_status,
        serpapi=serpapi_status,
        ollama=ollama_status,
        redis=redis_status,
    )

    print("[HEALTH] Status report:")
    print(f"  overall = {response.status!r}")
    print(f"  openai  = {response.openai!r}")
    print(f"  ollama  = {response.ollama!r}")
    print(f"  redis   = {response.redis!r}")
    print(f"  serpapi = {response.serpapi!r}")
    print("=" * 60 + "\n")

    return response
