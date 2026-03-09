"""Unit tests for app/prompts/*"""

from app.prompts.intent_extraction import build_intent_prompt
from app.prompts.product_ranking import build_ranking_prompt
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


def test_intent_prompt_structure():
    messages = build_intent_prompt("budget gaming chair")
    assert isinstance(messages, list)
    assert messages[0]["role"] == "system"
    assert messages[-1]["content"] == "budget gaming chair"


def test_ranking_prompt_embeds_products():
    products = [{"title": "Chair A", "price": "$199"}]
    messages = build_ranking_prompt("gaming chair", products)
    assert len(messages) == 2
    assert "Chair A" in messages[-1]["content"]
