"""Version 1 route aggregation."""

from fastapi import APIRouter

from app.routes.v1 import health, query

router = APIRouter(prefix="/v1")
router.include_router(health.router, tags=["Health"])
router.include_router(query.router, tags=["Query"])
