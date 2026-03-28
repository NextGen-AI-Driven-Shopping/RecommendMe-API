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
                            "content": '{"classification": "VAGUE", "follow_ups": ["What is your budget?", "What features do you need?", "Any brand preferences?"]}'
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

    monkeypatch.setattr("app.services.vagueness.httpx.AsyncClient", _FakeClient)

    result = asyncio.run(classify_vagueness("need a laptop", allow_fallback=False))

    assert result.classification == "VAGUE"
    assert result.follow_ups is not None
    assert len(result.follow_ups) == 3


def test_classify_vagueness_marks_broad_activity_query_as_vague():
    result = asyncio.run(classify_vagueness("i am going for trekking", allow_fallback=False))

    assert result.classification == "VAGUE"
    assert result.provider == "Heuristic"
