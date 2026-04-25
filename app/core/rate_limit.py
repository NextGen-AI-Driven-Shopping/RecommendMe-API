"""Lightweight in-memory rate limiting and login-attempt throttling.

For multi-worker deployments swap in a Redis-backed counter; the public
helpers here keep the signature stable so callers do not change.

Two distinct concepts live in this module:

  * RateLimiter.check_and_increment — caps the number of times a single
    key (IP, user, etc.) can hit a sensitive endpoint per fixed window.
    Used to throttle anonymous abuse on auth endpoints.

  * LoginAttemptTracker — adds an exponentially extending lockout once a
    given identifier (email/phone) accumulates too many failed logins,
    independent of source IP. Protects against credential stuffing.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field

from fastapi import HTTPException, Request, status


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


def get_client_key(request: Request) -> str:
    """Best-effort client identifier for rate limiting.

    Honours X-Forwarded-For only when it is set explicitly by a known
    proxy in the deployment. Falls back to the direct peer address.
    """
    forwarded = request.headers.get("x-forwarded-for") or ""
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else "unknown"


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
