"""
Shared pytest fixtures for the RecommendMe API test suite.

Provides:
  - A synchronous TestClient wrapping the FastAPI app.
  - A minimal valid query request payload.
  - Placeholder fixtures for mocking OpenAI and SerpAPI clients.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    """Return a synchronous TestClient wrapping the FastAPI application."""
    return TestClient(app)


@pytest.fixture
def mock_query_request() -> dict:
    """Return a minimal valid POST /v1/query request payload."""
    return {
        "query": "best wireless headphones under $100",
        "session_id": None,
        "conversation": [],
    }


@pytest.fixture
def mock_vague_query_request() -> dict:
    """Return a query payload that should trigger a VAGUE classification."""
    return {"query": "something nice"}
