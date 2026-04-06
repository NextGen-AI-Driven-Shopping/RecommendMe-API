"""Integration tests for CSV-backed auth endpoints."""

import asyncio
from pathlib import Path

import httpx

from app.main import app


def _post(path: str, payload: dict) -> httpx.Response:
    async def _request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post(path, json=payload)

    return asyncio.run(_request())


def test_signup_and_login_flow(tmp_path: Path, monkeypatch):
    csv_path = tmp_path / "users.csv"
    auth_service = __import__("app.routes.v1.auth", fromlist=["auth_service"]).auth_service
    monkeypatch.setattr(auth_service, "csv_path", csv_path)
    auth_service._ensure_csv_file()

    signup_payload = {
        "username": "alice01",
        "first_name": "Alice",
        "last_name": "Walker",
        "email": "alice@example.com",
        "phone": "+1 555 123 7890",
        "password": "Secr3t!Pass",
    }

    signup_response = _post("/v1/auth/signup", signup_payload)
    assert signup_response.status_code == 200
    signup_data = signup_response.json()
    assert signup_data["user"]["email"] == "alice@example.com"
    assert signup_data["user"]["phone"].startswith("+1")

    login_response = _post("/v1/auth/login", {"identifier": "alice@example.com", "password": "Secr3t!Pass"})
    assert login_response.status_code == 200
    login_data = login_response.json()
    assert login_data["token"]
    assert login_data["user"]["username"] == "alice01"


def test_login_returns_not_found_for_new_user(tmp_path: Path, monkeypatch):
    csv_path = tmp_path / "users.csv"
    auth_service = __import__("app.routes.v1.auth", fromlist=["auth_service"]).auth_service
    monkeypatch.setattr(auth_service, "csv_path", csv_path)
    auth_service._ensure_csv_file()

    response = _post("/v1/auth/login", {"identifier": "new@user.com", "password": "secret123"})
    assert response.status_code == 404


def test_signup_rejects_duplicate_email(tmp_path: Path, monkeypatch):
    csv_path = tmp_path / "users.csv"
    auth_service = __import__("app.routes.v1.auth", fromlist=["auth_service"]).auth_service
    monkeypatch.setattr(auth_service, "csv_path", csv_path)
    auth_service._ensure_csv_file()

    payload = {
        "username": "bob01",
        "first_name": "Bob",
        "last_name": "Lee",
        "email": "bob@example.com",
        "phone": "",
        "password": "Secret123!",
    }

    first = _post("/v1/auth/signup", payload)
    second = _post("/v1/auth/signup", payload)
    assert first.status_code == 200
    assert second.status_code == 409
