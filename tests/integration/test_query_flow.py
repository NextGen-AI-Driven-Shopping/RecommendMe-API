"""Integration tests for POST /v1/query with mocked upstream services."""

import asyncio
from dataclasses import dataclass

import httpx

from app.main import app
from app.models.responses import ProductCard
from app.providers.base import RecommendedProductInfo


def _post(path: str, payload: dict) -> httpx.Response:
    async def _request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post(path, json=payload)

    return asyncio.run(_request())


@dataclass
class _FakeVagueness:
    classification: str
    follow_ups: list[str] | None = None


@dataclass
class _FakeCategoryPlan:
    categories: list[str]
    reasoning: str
    recommended_products: list[RecommendedProductInfo]


def test_vague_query_returns_clarification(monkeypatch):
    async def _fake_classify_vagueness(query: str, allow_fallback: bool = True):
        return _FakeVagueness(
            classification="VAGUE",
            follow_ups=["What budget range should I target?"],
        )

    monkeypatch.setattr("app.routes.v1.query.classify_vagueness", _fake_classify_vagueness)

    response = _post("/v1/query", {"user_message": "help", "conversation_history": []})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "clarification_needed"
    assert "budget" in data["message"].lower()
    assert data["session_id"]


def test_clear_query_returns_recommendations(monkeypatch):
    async def _fake_classify_vagueness(query: str, allow_fallback: bool = True):
        return _FakeVagueness(classification="CLEAR")

    async def _fake_generate_category_plan(query: str, context=None):
        return _FakeCategoryPlan(
            categories=["lightweight trekking backpack"],
            reasoning="Budget-friendly trekking setup.",
            recommended_products=[
                RecommendedProductInfo(
                    name="Trekking Backpack 35L",
                    explanation="Perfect for day hikes",
                    label="Recommended"
                )
            ],
        )

    async def _fake_fetch_products(category: str, query: str):
        return [
            ProductCard(
                title="Pack A",
                price="$89",
                url="https://example.com/a",
                image_url=None,
                source="Retailer",
                rating=4.5,
            )
        ]

    monkeypatch.setattr("app.routes.v1.query.classify_vagueness", _fake_classify_vagueness)
    monkeypatch.setattr("app.routes.v1.query.generate_category_plan", _fake_generate_category_plan)
    monkeypatch.setattr("app.routes.v1.query.fetch_products", _fake_fetch_products)

    response = _post(
        "/v1/query",
        {
            "user_message": "I need lightweight trekking gear under 150 dollars",
            "conversation_history": [{"role": "user", "content": "trekking gear"}],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "recommendations"
    assert len(data["categories"]) == 1
    assert data["categories"][0]["products"][0]["url"].startswith("https://")


def test_clear_query_uses_local_product_fallback_when_fetch_fails(monkeypatch):
    async def _fake_classify_vagueness(query: str, allow_fallback: bool = True):
        return _FakeVagueness(classification="CLEAR")

    async def _fake_generate_category_plan(query: str, context=None):
        return _FakeCategoryPlan(
            categories=["camping stove"],
            reasoning="Cooking essentials for trekking.",
            recommended_products=[
                RecommendedProductInfo(
                    name="Portable Camping Stove",
                    explanation="Lightweight and compact",
                    label="Recommended"
                )
            ],
        )

    async def _fake_fetch_products(category: str, query: str):
        return None

    monkeypatch.setattr("app.routes.v1.query.classify_vagueness", _fake_classify_vagueness)
    monkeypatch.setattr("app.routes.v1.query.generate_category_plan", _fake_generate_category_plan)
    monkeypatch.setattr("app.routes.v1.query.fetch_products", _fake_fetch_products)

    response = _post("/v1/query", {"user_message": "I need a lightweight stove for trekking"})

    assert response.status_code == 200
    data = response.json()
    product = data["categories"][0]["products"][0]
    assert product["url"].startswith("https://www.google.com/search?q=")
    assert "live listings unavailable" in product["explanation"].lower()


def test_sufficiency_check_returns_stage_metadata():
    response = _post(
        "/v1/query/sufficiency_check",
        {
            "user_message": "headphones",
            "clarification": [
                {"question": "Main use?", "answer": "work calls"},
                {"question": "Type?", "answer": "over-ear"},
                {"question": "Budget?", "answer": "under $100"},
            ],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "sufficient" in data
    assert "score" in data
    assert data["clarification_round"] in (1, 2)
    assert data["max_total_questions"] == 5
