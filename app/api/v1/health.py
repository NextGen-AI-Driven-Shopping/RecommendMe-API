"""
Health check route handler — GET /v1/health.

Returns the current system status, including connectivity checks
for OpenAI, Ollama, and Redis.
"""

from fastapi import APIRouter

from app.models.responses import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Return system health status.

    Liveness probe used by Railway, Docker Compose, and Kubernetes.
    Extended dependency checks (Redis, Ollama, OpenAI) should be
    implemented here before production deployment.
    """
    return HealthResponse(status="ok")
