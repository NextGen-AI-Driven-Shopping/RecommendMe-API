"""Unit tests for app/services/vagueness.py"""

import asyncio

from app.services.vagueness import classify_vagueness


def test_classify_vagueness_returns_vague_with_followups(monkeypatch):
    class _FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "message": {
                    "content": '{"classification": "VAGUE", "follow_ups": ["What is your budget?", "What features do you need?", "Any brand preferences?"]}'
                }
            }

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            return _FakeResponse()

    class _FakeSettings:
        OLLAMA_URL = "http://localhost:11434"
        OLLAMA_MODEL = "llama3"

    monkeypatch.setattr("app.services.vagueness.httpx.AsyncClient", _FakeClient)
    monkeypatch.setattr("app.services.vagueness.get_settings", lambda: _FakeSettings())

    result = asyncio.run(classify_vagueness("need a laptop", allow_fallback=False))

    assert result.classification == "VAGUE"
    assert result.follow_ups is not None
    assert len(result.follow_ups) == 3
