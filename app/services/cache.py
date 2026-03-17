"""
In-memory caching service with Redis fallback.

Provides async get/set helpers for caching product query results
to reduce redundant SerpAPI calls and AI-processing overhead.

Cache key convention : "recommendations:{md5(normalized_query)}"
Default TTL          : 3600 seconds (1 hour), configurable via Settings.

NOTE: Production deployments should use Redis. This in-memory cache works
for single-instance deployments but will lose data across restarts.
"""

import json
from typing import Any
from datetime import datetime, timedelta

# In-memory cache with TTL support
_MEMORY_CACHE: dict[str, tuple[Any, float]] = {}


async def get_cached_result(key: str) -> Any | None:
    """
    Retrieve a cached value from in-memory cache.

    Args:
        key: Cache key string.

    Returns:
        Deserialized Python object, or None if not found / expired.
    """
    if key not in _MEMORY_CACHE:
        return None
    
    value, expiry_time = _MEMORY_CACHE[key]
    
    # Check if expired
    if datetime.now().timestamp() > expiry_time:
        del _MEMORY_CACHE[key]
        return None
    
    return value


async def set_cached_result(key: str, value: Any, ttl: int = 3600) -> None:
    """
    Store a JSON-serializable value in in-memory cache with a TTL.

    Args:
        key:   Cache key string.
        value: JSON-serializable value to store.
        ttl:   Time-to-live in seconds (default: 3600).
    """
    expiry_time = (datetime.now() + timedelta(seconds=ttl)).timestamp()
    _MEMORY_CACHE[key] = (value, expiry_time)


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
