"""Health check route handler for GET /v1/health."""

import asyncio

import httpx
import redis.asyncio as redis
from fastapi import APIRouter

from app.config.settings import get_settings
from app.core.logger import get_logger
from app.models.responses import HealthResponse

logger = get_logger(__name__)
router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return service health with lightweight provider probes."""
    settings = get_settings()

    openai_status = "configured" if settings.OPENAI_API_KEY else "not configured"
    gemini_status = "configured" if settings.GEMINI_API_KEY else "not configured"
    groq_status = "configured" if settings.GROQ_API_KEY else "not configured"
    serpapi_status = "configured" if settings.SERPAPI_KEY else "not configured"

    ollama_status = "not configured"
    if settings.OLLAMA_URL:
        try:
            async with httpx.AsyncClient(timeout=1.0) as client:
                resp = await client.get(f"{settings.OLLAMA_URL}/api/tags")
                ollama_status = "healthy" if resp.status_code == 200 else "unhealthy"
        except asyncio.TimeoutError:
            logger.warning("Ollama probe timed out")
            ollama_status = "timeout"
        except Exception as exc:
            logger.warning("Ollama probe failed: %s", exc)
            ollama_status = "unreachable"

    redis_status = "not configured"
    if settings.REDIS_URL:
        try:
            r = redis.from_url(settings.REDIS_URL, decode_responses=True)
            pong = await asyncio.wait_for(r.ping(), timeout=1.0)
            redis_status = "healthy" if pong else "unhealthy"
            await r.close()
        except asyncio.TimeoutError:
            logger.warning("Redis probe timed out")
            redis_status = "timeout"
        except Exception as exc:
            logger.warning("Redis probe failed: %s", exc)
            redis_status = "unreachable"

    return HealthResponse(
        status="ok",
        openai=openai_status,
        gemini=gemini_status,
        groq=groq_status,
        serpapi=serpapi_status,
        ollama=ollama_status,
        redis=redis_status,
    )
