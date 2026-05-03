"""Shared Redis client helper.

Returns a connected Redis client if REDIS_URL is set and reachable,
otherwise returns None so callers can fall back to in-memory defaults.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional

try:
    import redis as _redis_lib
    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False

from app.config.settings import get_settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_redis_client() -> "Optional[_redis_lib.Redis]":
    """Return a Redis client if configured and reachable, else None."""
    if not _REDIS_AVAILABLE:
        return None
    settings = get_settings()
    url = (settings.REDIS_URL or "").strip()
    if not url:
        return None
    try:
        client = _redis_lib.Redis.from_url(url, decode_responses=True, socket_connect_timeout=2)
        client.ping()
        return client
    except Exception as exc:
        logger.warning("Redis unavailable, falling back to in-memory: %s", exc)
        return None
