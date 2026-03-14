"""
Integration tests for GET /v1/health.

These tests run against the full FastAPI application stack
(no external services required).
"""

import asyncio

import httpx

from app.main import app


def _get(path: str) -> httpx.Response:
    async def _request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get(path)

    return asyncio.run(_request())


def test_health_returns_200():
    response = _get("/v1/health")
    assert response.status_code == 200


def test_health_returns_ok_status():
    response = _get("/v1/health")
    data = response.json()
    assert data["status"] == "ok"


def test_health_response_is_json():
    response = _get("/v1/health")
    assert response.headers["content-type"].startswith("application/json")
