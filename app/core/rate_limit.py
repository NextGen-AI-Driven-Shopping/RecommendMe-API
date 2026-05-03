"""Rate limiting and login-attempt throttling.

Two implementations are provided for each concept:

  * In-memory — works for single-instance deployments and local dev.
  * Redis-backed — required for multi-worker / multi-instance deployments
    so counters are shared across all workers.

Use the factory helpers `get_rate_limiter()` and `get_login_tracker()`
to get the appropriate implementation based on whether Redis is available.
Callers keep the same interface regardless of which backend is used.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field

from fastapi import HTTPException, Request, status

from app.core.redis_client import get_redis_client


# ── In-memory implementations (single-instance / local dev) ─────────────────

class RateLimiter:
    """Sliding-window counter keyed by an arbitrary string."""

    def __init__(self, *, max_requests: int, window_seconds: int) -> None:
        self._max = max(1, int(max_requests))
        self._window = max(1, int(window_seconds))
        self._buckets: dict[str, deque[float]] = {}
        self._lock = threading.RLock()

    def check_and_increment(self, key: str) -> tuple[bool, float]:
        """Return (allowed, retry_after_seconds)."""
        now = time.time()
        cutoff = now - self._window

        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = deque()
                self._buckets[key] = bucket

            while bucket and bucket[0] < cutoff:
                bucket.popleft()

            if len(bucket) >= self._max:
                retry_after = max(0.0, self._window - (now - bucket[0]))
                return False, retry_after

            bucket.append(now)
            return True, 0.0


@dataclass
class _AttemptRecord:
    failures: int = 0
    locked_until: float = 0.0
    history: deque[float] = field(default_factory=deque)


class LoginAttemptTracker:
    """Throttles repeated failed logins for a given identifier."""

    def __init__(
        self,
        *,
        max_failures: int = 5,
        window_seconds: int = 600,
        base_lockout_seconds: int = 60,
        max_lockout_seconds: int = 1800,
    ) -> None:
        self._max_failures = max(1, max_failures)
        self._window = max(1, window_seconds)
        self._base_lockout = max(1, base_lockout_seconds)
        self._max_lockout = max(self._base_lockout, max_lockout_seconds)
        self._records: dict[str, _AttemptRecord] = {}
        self._lock = threading.RLock()

    @staticmethod
    def _normalize(identifier: str) -> str:
        return (identifier or "").strip().lower()

    def assert_not_locked(self, identifier: str) -> None:
        key = self._normalize(identifier)
        if not key:
            return
        with self._lock:
            record = self._records.get(key)
            if record and record.locked_until > time.time():
                wait = int(record.locked_until - time.time())
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Too many failed attempts. Try again in {wait} seconds.",
                )

    def record_failure(self, identifier: str) -> None:
        key = self._normalize(identifier)
        if not key:
            return
        now = time.time()
        with self._lock:
            record = self._records.get(key) or _AttemptRecord()
            cutoff = now - self._window
            while record.history and record.history[0] < cutoff:
                record.history.popleft()
                if record.failures > 0:
                    record.failures -= 1

            record.failures += 1
            record.history.append(now)

            if record.failures >= self._max_failures:
                excess = record.failures - self._max_failures
                lockout = min(self._max_lockout, self._base_lockout * (2 ** excess))
                record.locked_until = now + lockout
            self._records[key] = record

    def record_success(self, identifier: str) -> None:
        key = self._normalize(identifier)
        if not key:
            return
        with self._lock:
            self._records.pop(key, None)


# ── Redis-backed implementations (multi-worker / production) ─────────────────

class RedisRateLimiter:
    """Sliding-window rate limiter backed by Redis sorted sets.

    Same interface as RateLimiter. Falls back to always-allowing if Redis
    is unavailable — the caller should prefer pairing this with a fallback.
    """

    def __init__(self, *, max_requests: int, window_seconds: int) -> None:
        self._max = max(1, int(max_requests))
        self._window = max(1, int(window_seconds))

    def check_and_increment(self, key: str) -> tuple[bool, float]:
        redis = get_redis_client()
        if not redis:
            return True, 0.0

        now = time.time()
        cutoff = now - self._window
        redis_key = f"rl:{key}"

        try:
            pipe = redis.pipeline()
            # Remove expired entries from the sorted set
            pipe.zremrangebyscore(redis_key, "-inf", cutoff)
            # Count remaining entries in the window
            pipe.zcard(redis_key)
            # Add current timestamp
            pipe.zadd(redis_key, {str(now): now})
            # Set key expiry so Redis auto-cleans idle keys
            pipe.expire(redis_key, self._window + 10)
            results = pipe.execute()

            count = results[1]
            if count >= self._max:
                # Get the oldest entry to compute retry_after
                oldest = redis.zrange(redis_key, 0, 0, withscores=True)
                retry_after = self._window - (now - oldest[0][1]) if oldest else float(self._window)
                return False, max(0.0, retry_after)

            return True, 0.0
        except Exception:
            return True, 0.0


class RedisLoginAttemptTracker:
    """Login attempt tracker backed by Redis.

    Same interface as LoginAttemptTracker. Falls back gracefully
    when Redis is unavailable (no lockout enforced — acceptable since
    the in-memory tracker is the baseline for dev environments).
    """

    def __init__(
        self,
        *,
        max_failures: int = 5,
        window_seconds: int = 600,
        base_lockout_seconds: int = 60,
        max_lockout_seconds: int = 1800,
    ) -> None:
        self._max_failures = max(1, max_failures)
        self._window = max(1, window_seconds)
        self._base_lockout = max(1, base_lockout_seconds)
        self._max_lockout = max(self._base_lockout, max_lockout_seconds)

    @staticmethod
    def _normalize(identifier: str) -> str:
        return (identifier or "").strip().lower()

    def _keys(self, identifier: str) -> tuple[str, str]:
        key = self._normalize(identifier)
        return f"login:failures:{key}", f"login:lockout:{key}"

    def assert_not_locked(self, identifier: str) -> None:
        redis = get_redis_client()
        if not redis:
            return
        _, lockout_key = self._keys(identifier)
        try:
            ttl = redis.ttl(lockout_key)
            if ttl and ttl > 0:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Too many failed attempts. Try again in {ttl} seconds.",
                )
        except HTTPException:
            raise
        except Exception:
            pass

    def record_failure(self, identifier: str) -> None:
        redis = get_redis_client()
        if not redis:
            return
        failures_key, lockout_key = self._keys(identifier)
        try:
            now = time.time()
            pipe = redis.pipeline()
            pipe.zadd(failures_key, {str(now): now})
            pipe.zremrangebyscore(failures_key, "-inf", now - self._window)
            pipe.expire(failures_key, self._window + 10)
            results = pipe.execute()

            count = results[1] if len(results) > 1 else redis.zcard(failures_key)
            # zremrangebyscore returns number removed; get current count
            count = redis.zcard(failures_key)

            if count >= self._max_failures:
                excess = count - self._max_failures
                lockout = min(self._max_lockout, self._base_lockout * (2 ** excess))
                redis.setex(lockout_key, int(lockout), "1")
        except Exception:
            pass

    def record_success(self, identifier: str) -> None:
        redis = get_redis_client()
        if not redis:
            return
        failures_key, lockout_key = self._keys(identifier)
        try:
            redis.delete(failures_key, lockout_key)
        except Exception:
            pass


# ── Factory helpers ───────────────────────────────────────────────────────────

def get_rate_limiter(*, max_requests: int, window_seconds: int) -> RateLimiter | RedisRateLimiter:
    """Return a Redis-backed rate limiter when Redis is available, else in-memory."""
    if get_redis_client():
        return RedisRateLimiter(max_requests=max_requests, window_seconds=window_seconds)
    return RateLimiter(max_requests=max_requests, window_seconds=window_seconds)


def get_login_tracker(
    *,
    max_failures: int = 5,
    window_seconds: int = 600,
    base_lockout_seconds: int = 60,
    max_lockout_seconds: int = 1800,
) -> LoginAttemptTracker | RedisLoginAttemptTracker:
    """Return a Redis-backed login tracker when Redis is available, else in-memory."""
    if get_redis_client():
        return RedisLoginAttemptTracker(
            max_failures=max_failures,
            window_seconds=window_seconds,
            base_lockout_seconds=base_lockout_seconds,
            max_lockout_seconds=max_lockout_seconds,
        )
    return LoginAttemptTracker(
        max_failures=max_failures,
        window_seconds=window_seconds,
        base_lockout_seconds=base_lockout_seconds,
        max_lockout_seconds=max_lockout_seconds,
    )


# ── Shared helpers ────────────────────────────────────────────────────────────

def get_client_key(request: Request) -> str:
    """Best-effort client identifier for rate limiting.

    Honours X-Forwarded-For only when set by a trusted proxy.
    Falls back to the direct peer address.
    """
    forwarded = request.headers.get("x-forwarded-for") or ""
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else "unknown"
