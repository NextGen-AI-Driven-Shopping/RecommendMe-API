"""Unit tests for app/utils/formatters.py"""

from app.utils.formatters import build_clarification_response, build_recommendation_response


def test_recommendation_response_has_correct_status():
    response = build_recommendation_response(categories=[], session_id="test-session")
    assert response.status == "recommendations"


def test_recommendation_response_carries_session_id():
    response = build_recommendation_response(categories=[], session_id="abc-123")
    assert response.session_id == "abc-123"


def test_recommendation_response_categories_default_empty():
    response = build_recommendation_response(categories=[])
    assert response.categories == []


def test_clarification_response_has_correct_status():
    response = build_clarification_response("What is your budget?")
    assert response.status == "clarification_needed"


def test_clarification_response_carries_message():
    response = build_clarification_response("What is your budget?")
    assert response.message is not None
    assert "budget" in response.message


def test_clarification_response_session_id_optional():
    response = build_clarification_response("More details?", session_id=None)
    assert response.session_id is None
