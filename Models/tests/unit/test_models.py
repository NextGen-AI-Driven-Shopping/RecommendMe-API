"""
Unit tests for Pydantic models in app.models
"""

import pytest
from pydantic import ValidationError

from app.models.requests import ConversationMessage, QueryRequest
from app.models.responses import (
    CategoryResult,
    ErrorResponse,
    FollowUpResponse,
    ProductCard,
    RecommendationResponse,
)
from app.models.internal import (
    ExtractedIntent,
    ProductSearchQuery,
    RankedProduct,
    VaguenessResult,
)


# =====================================================================
# ConversationMessage
# =====================================================================

class TestConversationMessage:

    def test_valid_user_message(self):
        msg = ConversationMessage(role="user", content="Hello there")
        assert msg.role == "user"
        assert msg.content == "Hello there"

    def test_valid_assistant_message(self):
        msg = ConversationMessage(role="assistant", content="How can I help?")
        assert msg.role == "assistant"

    def test_invalid_role_rejected(self):
        with pytest.raises(ValidationError):
            ConversationMessage(role="system", content="test")

    def test_empty_content_rejected(self):
        with pytest.raises(ValidationError):
            ConversationMessage(role="user", content="")

    def test_content_stripped(self):
        msg = ConversationMessage(role="user", content="  hello world  ")
        assert msg.content == "hello world"

    def test_content_too_long_rejected(self):
        with pytest.raises(ValidationError):
            ConversationMessage(role="user", content="x" * 2001)

    def test_content_at_max_length_passes(self):
        msg = ConversationMessage(role="user", content="x" * 2000)
        assert len(msg.content) == 2000


# =====================================================================
# QueryRequest
# =====================================================================

class TestQueryRequest:

    def test_valid_request(self):
        req = QueryRequest(
            user_message="I want to buy a tent for camping",
            conversation_history=[],
        )
        assert req.user_message == "I want to buy a tent for camping"
        assert req.session_id is None
        assert req.conversation_history == []

    def test_user_message_stripped(self):
        req = QueryRequest(user_message="  I want to buy stuff  ")
        assert req.user_message == "I want to buy stuff"

    def test_session_id_optional(self):
        req = QueryRequest(user_message="I need a new laptop")
        assert req.session_id is None

    def test_session_id_accepted(self):
        req = QueryRequest(
            session_id="550e8400-e29b-41d4-a716-446655440000",
            user_message="I need a laptop for programming",
        )
        assert str(req.session_id) == "550e8400-e29b-41d4-a716-446655440000"

    def test_too_few_words_rejected(self):
        with pytest.raises(ValidationError, match="at least 3 words"):
            QueryRequest(user_message="hi there")

    def test_single_word_rejected(self):
        with pytest.raises(ValidationError, match="at least 3 words"):
            QueryRequest(user_message="laptop")

    def test_empty_message_rejected(self):
        with pytest.raises(ValidationError):
            QueryRequest(user_message="")

    def test_conversation_history_max_20(self):
        messages = [
            ConversationMessage(role="user", content=f"msg {i}")
            for i in range(21)
        ]
        with pytest.raises(ValidationError):
            QueryRequest(
                user_message="I want a tent for camping",
                conversation_history=messages,
            )

    def test_conversation_history_at_20_passes(self):
        messages = [
            ConversationMessage(role="user", content=f"message number {i}")
            for i in range(20)
        ]
        req = QueryRequest(
            user_message="I want a tent for camping",
            conversation_history=messages,
        )
        assert len(req.conversation_history) == 20

    def test_default_empty_history(self):
        req = QueryRequest(user_message="I need some new headphones")
        assert req.conversation_history == []


# =====================================================================
# ProductCard
# =====================================================================

class TestProductCard:

    @pytest.fixture
    def valid_product_data(self):
        return {
            "title": "Quechua 2-Person Tent MH100",
            "price": "₹3,499",
            "rating": 4.5,
            "reviews": "2,140",
            "source": "Decathlon",
            "link": "https://decathlon.in/tent-mh100",
            "reason": "Best weight-to-price ratio.",
        }

    def test_valid_product(self, valid_product_data):
        product = ProductCard(**valid_product_data)
        assert product.title == "Quechua 2-Person Tent MH100"
        assert product.rating == 4.5

    def test_rating_zero_passes(self, valid_product_data):
        valid_product_data["rating"] = 0.0
        product = ProductCard(**valid_product_data)
        assert product.rating == 0.0

    def test_rating_five_passes(self, valid_product_data):
        valid_product_data["rating"] = 5.0
        product = ProductCard(**valid_product_data)
        assert product.rating == 5.0

    def test_rating_above_five_rejected(self, valid_product_data):
        valid_product_data["rating"] = 5.1
        with pytest.raises(ValidationError):
            ProductCard(**valid_product_data)

    def test_rating_negative_rejected(self, valid_product_data):
        valid_product_data["rating"] = -0.1
        with pytest.raises(ValidationError):
            ProductCard(**valid_product_data)

    def test_invalid_link_rejected(self, valid_product_data):
        valid_product_data["link"] = "not-a-url"
        with pytest.raises(ValidationError):
            ProductCard(**valid_product_data)

    def test_thumbnail_optional(self, valid_product_data):
        product = ProductCard(**valid_product_data)
        assert product.thumbnail is None

    def test_missing_title_rejected(self, valid_product_data):
        del valid_product_data["title"]
        with pytest.raises(ValidationError):
            ProductCard(**valid_product_data)


# =====================================================================
# FollowUpResponse
# =====================================================================

class TestFollowUpResponse:

    def test_valid_followup(self):
        resp = FollowUpResponse(
            questions=["Where are you going?", "What's your budget?"]
        )
        assert resp.type == "followup"
        assert len(resp.questions) == 2

    def test_type_is_always_followup(self):
        resp = FollowUpResponse(questions=["test question here?"])
        assert resp.type == "followup"

    def test_empty_questions_rejected(self):
        with pytest.raises(ValidationError):
            FollowUpResponse(questions=[])

    def test_questions_stripped(self):
        resp = FollowUpResponse(questions=["  Where are you going?  "])
        assert resp.questions[0] == "Where are you going?"

    def test_max_five_questions(self):
        questions = [f"Question {i}?" for i in range(6)]
        with pytest.raises(ValidationError):
            FollowUpResponse(questions=questions)


# =====================================================================
# RecommendationResponse
# =====================================================================

class TestRecommendationResponse:

    @pytest.fixture
    def valid_category(self):
        return CategoryResult(
            name="Tent",
            why_needed="Essential for camping.",
            products=[
                ProductCard(
                    title="Test Tent",
                    price="₹3,499",
                    rating=4.5,
                    reviews="100",
                    source="Amazon",
                    link="https://amazon.in/tent",
                    reason="Good value.",
                ),
            ],
        )

    def test_valid_recommendation(self, valid_category):
        resp = RecommendationResponse(
            summary="Gear for a camping trip.",
            categories=[valid_category],
        )
        assert resp.type == "recommendations"
        assert len(resp.categories) == 1

    def test_type_is_always_recommendations(self, valid_category):
        resp = RecommendationResponse(
            summary="Gear ready.",
            categories=[valid_category],
        )
        assert resp.type == "recommendations"

    def test_empty_categories_rejected(self, valid_category):
        with pytest.raises(ValidationError):
            RecommendationResponse(summary="Nothing.", categories=[])


# =====================================================================
# ErrorResponse
# =====================================================================

class TestErrorResponse:

    def test_valid_error(self):
        err = ErrorResponse(
            code="QUERY_TOO_SHORT",
            message="Your query is too short.",
        )
        assert err.error is True
        assert err.retry_after is None

    def test_with_retry_after(self):
        err = ErrorResponse(
            code="OPENAI_RATE_LIMIT",
            message="Busy.",
            retry_after=5,
        )
        assert err.retry_after == 5

    def test_error_field_always_true(self):
        err = ErrorResponse(code="TEST", message="test")
        assert err.error is True


# =====================================================================
# Internal models
# =====================================================================

class TestVaguenessResult:

    def test_clear_result(self):
        result = VaguenessResult(is_clear=True, confidence=0.95)
        assert result.is_clear is True
        assert result.follow_up_questions is None

    def test_vague_result_with_questions(self):
        result = VaguenessResult(
            is_clear=False,
            follow_up_questions=["Where?", "Budget?"],
            confidence=0.8,
        )
        assert result.is_clear is False
        assert len(result.follow_up_questions) == 2

    def test_confidence_bounds(self):
        with pytest.raises(ValidationError):
            VaguenessResult(is_clear=True, confidence=1.5)
        with pytest.raises(ValidationError):
            VaguenessResult(is_clear=True, confidence=-0.1)


class TestExtractedIntent:

    def test_valid_intent(self):
        intent = ExtractedIntent(
            original_query="I want to go trekking",
            resolved_context="3-day trek in Himachal, camping, budget ₹15000",
            categories=["Tent", "Sleeping Bag", "Backpack"],
        )
        assert len(intent.categories) == 3

    def test_empty_categories_rejected(self):
        with pytest.raises(ValidationError):
            ExtractedIntent(
                original_query="test",
                resolved_context="test",
                categories=[],
            )


class TestProductSearchQuery:

    def test_valid_query(self):
        q = ProductSearchQuery(
            category="Tent",
            search_terms=["camping tent", "2 person tent"],
            max_price=5000.0,
            min_rating=4.0,
        )
        assert q.category == "Tent"
        assert q.max_price == 5000.0

    def test_price_optional(self):
        q = ProductSearchQuery(
            category="Tent",
            search_terms=["tent"],
        )
        assert q.max_price is None

    def test_rating_bounds(self):
        with pytest.raises(ValidationError):
            ProductSearchQuery(
                category="Tent",
                search_terms=["tent"],
                min_rating=6.0,
            )


class TestRankedProduct:

    def test_valid_ranked_product(self):
        rp = RankedProduct(
            title="Test Tent",
            price="₹3,499",
            rating=4.5,
            reviews="100",
            source="Amazon",
            link="https://amazon.in/tent",
            reason="Best value.",
            rank=1,
            score=0.95,
        )
        assert rp.rank == 1
        assert rp.score == 0.95

    def test_rank_must_be_positive(self):
        with pytest.raises(ValidationError):
            RankedProduct(
                title="T", price="₹1", rating=4.0, reviews="1",
                source="A", link="https://a.com", reason="R",
                rank=0, score=0.5,
            )

    def test_score_bounds(self):
        with pytest.raises(ValidationError):
            RankedProduct(
                title="T", price="₹1", rating=4.0, reviews="1",
                source="A", link="https://a.com", reason="R",
                rank=1, score=1.5,
            )
