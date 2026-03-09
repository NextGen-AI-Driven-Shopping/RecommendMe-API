"""
Redis caching service.

Provides async get/set helpers for caching product query results
to reduce redundant SerpAPI calls and AI-processing overhead.

Cache key convention : "recommendations:{md5(normalized_query)}"
Default TTL          : 3 600 seconds (1 hour), configurable via Settings.
"""

import json
from typing import Any


async def get_cached_result(key: str) -> Any | None:
    """
    Retrieve a cached value from Redis.

    Args:
        key: Cache key string.

    Returns:
        Deserialized Python object, or None if not found / expired.
    """
    # TODO: obtain Redis client from app state and call GET
    pass


async def set_cached_result(key: str, value: Any, ttl: int = 3600) -> None:
    """
    Store a JSON-serializable value in Redis with a TTL.

    Args:
        key:   Cache key string.
        value: JSON-serializable value to store.
        ttl:   Time-to-live in seconds (default: 3 600).
    """
    # TODO: obtain Redis client from app state and call SETEX
    pass


def build_cache_key(query: str) -> str:
    """
    Generate a stable cache key from a normalized query string.

    Args:
        query: User query string.

    Returns:
        Cache key in the form "recommendations:{md5_hex}".
    """
    import hashlib

    normalized = query.strip().lower()
    digest = hashlib.md5(normalized.encode()).hexdigest()  # noqa: S324 — non-crypto use
    return f"recommendations:{digest}"
