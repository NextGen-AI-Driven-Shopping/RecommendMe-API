"""Version 1 route aggregation."""

from fastapi import APIRouter

from app.routes.v1 import auth, chat_mode, health, profile, query, sessions

router = APIRouter(prefix="/v1")
router.include_router(health.router, tags=["Health"])
router.include_router(query.router, tags=["Query"])
router.include_router(auth.router, tags=["Auth"])
router.include_router(profile.router, tags=["Profile"])
router.include_router(sessions.router, tags=["Sessions"])
router.include_router(chat_mode.router, tags=["ChatMode"])
