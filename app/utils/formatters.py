"""
Response formatting utilities — aligned to Flow.md.

Assembles final QueryResponse objects for all pipeline states.
"""

from __future__ import annotations

from typing import List, Optional

from app.models.responses import (
    ProductItemResponse,
    ProductTypeResponse,
    QueryResponse,
    QuestionOptionResponse,
)
from app.models.internal import (
    ProductType,
    QuestionWithOptions,
    RecommendationResult,
)


def build_recommendation_response(
    *,
    result: RecommendationResult,
    session_id: str | None = None,
    summary: str | None = None,
    category: str | None = None,
) -> QueryResponse:
    """
    Assemble a successful recommendations response from the pipeline result.

    Converts internal models to API response models.
    """
    product_type_responses = []
    for pt in result.product_types:
        items = [
            ProductItemResponse(
                product_name=item.product_name,
                image_url=item.image_url,
                price_inr=item.price_inr,
                short_description=item.short_description,
                buy_link=item.buy_link,
                rating=item.rating,
                brand=item.brand,
                reviews_count=item.reviews_count,
                delivery_info=item.delivery_info,
                availability=item.availability,
                source=item.source,
            )
            for item in pt.valid_items
        ]
        product_type_responses.append(
            ProductTypeResponse(
                product_type=pt.product_type,
                description=pt.description,
                product_items=items,
                serp_error=pt.serp_error,
                serp_error_message=pt.serp_error_message,
            )
        )

    return QueryResponse(
        status="recommendations",
        category=result.category,
        product_types=product_type_responses,
        summary=summary,
        session_id=session_id,
    )


def build_clarification_response(
    *,
    questions: list[QuestionWithOptions],
    session_id: str | None = None,
    clarification_round: int = 1,
    asked_questions: int = 0,
    max_total_questions: int = 5,
) -> QueryResponse:
    """
    Assemble a clarification-needed response with questions and options.
    """
    question_responses = [
        QuestionOptionResponse(
            question=q.question,
            options=q.options,
        )
        for q in questions
    ]

    # Build a message from all questions
    message = "\n".join(f"• {q.question}" for q in questions)

    return QueryResponse(
        status="clarification_needed",
        message=message,
        questions=question_responses,
        session_id=session_id,
        clarification_round=clarification_round,
        asked_questions=asked_questions,
        max_total_questions=max_total_questions,
    )


def build_preclarification_response(
    *,
    question: QuestionWithOptions,
    session_id: str | None = None,
) -> QueryResponse:
    """Assemble a pre-clarification response (Step 2.5)."""
    return QueryResponse(
        status="pre_clarification",
        message=question.question,
        questions=[QuestionOptionResponse(
            question=question.question,
            options=question.options,
        )],
        session_id=session_id,
        clarification_round=0,
        asked_questions=0,
        max_total_questions=5,
    )


def build_out_of_scope_response(
    *,
    message: str,
    session_id: str | None = None,
) -> QueryResponse:
    """
    Assemble an out-of-scope response when the query cannot produce recommendations.
    """
    return QueryResponse(
        status="out_of_scope",
        message=message,
        session_id=session_id,
    )


def build_error_response(
    *,
    message: str,
    session_id: str | None = None,
) -> QueryResponse:
    """Assemble an error response with a user-friendly message."""
    return QueryResponse(
        status="error",
        message=message,
        session_id=session_id,
    )
