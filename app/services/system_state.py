"""
Global system-state tracking for the recommendation pipeline.

This module holds process-lifetime state that must survive across individual
HTTP requests:

  system_state["serpapi_available"]
      Set to False the moment SerpAPI returns HTTP 429 (quota exhausted).
      Stays False for the remainder of the process — no blind retry on the
      next request.  Restart the process (or re-deploy) to reset.

  system_state["last_quota_error"]
      ISO-8601 timestamp of the most recent 429 so operators can correlate
      logs without digging through the full log stream.

Constants exposed here are imported by products.py and query.py so that
request-budget limits and retry counts are configured in one place.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

# ── Process-Lifetime State ────────────────────────────────────────────────────

system_state: dict[str, Any] = {
    "serpapi_available": True,
    "last_quota_error": None,   # ISO-8601 string set on first 429
}


def mark_serpapi_quota_exhausted() -> None:
    """
    Permanently disable SerpAPI for the remaining lifetime of this process.

    Call this immediately when you receive HTTP 429 from SerpAPI.
    After this call, ``system_state["serpapi_available"]`` is False and
    products.py will skip SerpAPI entirely on every subsequent call.
    """
    system_state["serpapi_available"] = False
    system_state["last_quota_error"] = datetime.now(timezone.utc).isoformat()


def is_serpapi_available() -> bool:
    """Return True only if SerpAPI has not yet exhausted its quota."""
    return bool(system_state["serpapi_available"])


# ── Per-Request Budget & Retry Constants ─────────────────────────────────────

# Maximum number of outgoing fetch_products() calls allowed per HTTP request.
# Prevents runaway loops when many categories / products are planned.
MAX_API_CALLS: int = 5

# Maximum retry attempts per individual API call.
# 1 means one initial attempt + one retry on transient failure only.
MAX_RETRIES: int = 1
