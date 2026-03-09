"""
Integration tests for GET /v1/health.

These tests run against the full FastAPI application stack
(no external services required).
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_200():
    response = client.get("/v1/health")
    assert response.status_code == 200


def test_health_returns_ok_status():
    response = client.get("/v1/health")
    data = response.json()
    assert data["status"] == "ok"


def test_health_response_is_json():
    response = client.get("/v1/health")
    assert response.headers["content-type"].startswith("application/json")
