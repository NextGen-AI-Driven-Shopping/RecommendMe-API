"""Unit tests for app/prompts/*"""

from app.prompts.category_reasoning import build_category_reasoning_messages
from app.prompts.vagueness_check import build_vagueness_prompt


def test_vagueness_prompt_has_system_message():
    messages = build_vagueness_prompt("best laptop for students")
    assert messages[0]["role"] == "system"


def test_vagueness_prompt_ends_with_user_query():
    messages = build_vagueness_prompt("best laptop for students")
    assert messages[-1]["role"] == "user"
    assert messages[-1]["content"] == "best laptop for students"


def test_vagueness_prompt_injects_context():
    context = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
    messages = build_vagueness_prompt("best laptop", context=context)
    assert len(messages) == 4  # system + 2 context + user


def test_category_prompt_structure():
    messages = build_category_reasoning_messages("budget gaming chair")
    assert isinstance(messages, list)
    assert messages[0]["role"] == "system"
    assert messages[-1]["content"] == "budget gaming chair"
