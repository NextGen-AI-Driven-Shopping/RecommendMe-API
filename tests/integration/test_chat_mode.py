"""Integration tests for post-results chat mode endpoint."""

import asyncio

import httpx

from app.main import app


def _post(path: str, payload: dict) -> httpx.Response:
    async def _request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post(path, json=payload)

    return asyncio.run(_request())


def _put_session(session_id: str, payload: dict) -> None:
    from app.utils.session import set_session

    set_session(session_id, payload)


def test_chat_mode_returns_contextual_answer_for_existing_recommendations():
    session_id = "chat-mode-session-1"
    _put_session(
        session_id,
        {
            "session_id": session_id,
            "status": "recommendations",
            "title": "Test Session",
            "messages": [],
            "categories": [
                {
                    "category": "Bags",
                    "products": [
                        {
                            "title": "Waterproof Trekking Backpack",
                            "price": "₹3999",
                            "explanation": "Waterproof shell with rain cover for mountain use.",
                            "url": "https://example.com/bag",
                        }
                    ],
                }
            ],
        },
    )

    response = _post(
        "/v1/chat/mode",
        {"session_id": session_id, "user_message": "Which one is waterproof?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == session_id
    assert "waterproof" in body["message"].lower()


def test_chat_mode_returns_error_without_recommendation_context():
    session_id = "chat-mode-session-2"
    _put_session(
        session_id,
        {
            "session_id": session_id,
            "status": "new",
            "title": "No Recommendations",
            "messages": [],
        },
    )

    response = _post(
        "/v1/chat/mode",
        {"session_id": session_id, "user_message": "Any options?"},
    )

    assert response.status_code == 400
