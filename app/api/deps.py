"""
Shared FastAPI dependencies.

Provides reusable Depends() callables injected into route handlers:
  - Session store access.
  - Rate limiter enforcement.

Add new application-wide dependencies here rather than importing
directly inside route modules.
"""

from fastapi import Request


def get_session(request: Request) -> dict:
    """Inject the in-memory session store from application state."""
    if not hasattr(request.app.state, "session_store"):
        request.app.state.session_store = {}
    return request.app.state.session_store


def get_rate_limiter(request: Request):
    """
    Inject the rate limiter into a route handler.

    Placeholder — wire up a real limiter (e.g. slowapi) here.
    """
    pass
