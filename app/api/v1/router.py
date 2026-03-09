"""
Version 1 API router.

Aggregates all v1 route modules into a single APIRouter that is
mounted on the main FastAPI application with the /v1 prefix.
"""

from fastapi import APIRouter

from app.api.v1 import health, query

router = APIRouter()

router.include_router(health.router, tags=["Health"])
router.include_router(query.router, tags=["Query"])
