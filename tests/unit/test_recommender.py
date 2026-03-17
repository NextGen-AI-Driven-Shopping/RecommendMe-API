"""Unit tests for app/services/recommender.py"""

from app.services.recommender import _normalize_context


def test_normalize_context_accepts_dict_and_object_messages():
    class Msg:
        role = "assistant"
        content = "  hello from assistant  "

    normalized = _normalize_context(
        [
            {"role": "user", "content": "  first message  "},
            Msg(),
        ]
    )

    assert normalized == [
        {"role": "user", "content": "first message"},
        {"role": "assistant", "content": "hello from assistant"},
    ]


def test_normalize_context_skips_empty_content_entries():
    normalized = _normalize_context(
        [
            {"role": "user", "content": "   "},
            {"role": "assistant", "content": None},
            {"role": "user", "content": "valid"},
        ]
    )

    assert normalized == [{"role": "user", "content": "valid"}]
