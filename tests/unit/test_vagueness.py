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
                "choices": [
                    {
                        "message": {
                            "content": '{"classification": "VAGUE", "follow_ups": ["What is your budget range? Under ₹2,000, ₹2,000–₹5,000, or above ₹5,000?", "What will you mainly use the laptop for? Coding, gaming, editing, or general work?", "Which platform do you prefer? Windows, macOS, or Linux-ready?"]}'
                        }
                    }
                ]
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
        GROQ_API_KEY = "test-key"
        GROQ_MODEL = "gpt-oss-120b"
        GROQ_MODELS = ["gpt-oss-120b"]

    monkeypatch.setattr("app.services.vagueness.httpx.AsyncClient", _FakeClient)
    monkeypatch.setattr("app.services.vagueness.get_settings", lambda: _FakeSettings())

    result = asyncio.run(classify_vagueness("need a laptop", allow_fallback=False))

    assert result.classification == "VAGUE"
    assert result.follow_ups is not None
    assert len(result.follow_ups) == 3
