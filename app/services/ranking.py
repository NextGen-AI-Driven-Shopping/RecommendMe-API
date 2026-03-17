"""
Product ranking service.

Calls GPT-4o to select the top-3 products from a raw SerpAPI result set,
add reasoning for each choice, and generate an expert shopping tip.

Usage
-----
    service = RankingService()
    ranked = service.rank_products(raw_products, user_context="gaming laptop")

Note: This service is synchronous.  Wrap calls in asyncio.to_thread() when
invoking from an async route handler until an async version is implemented.
"""

import os
import random
import time
from typing import Any

import openai

from app.prompts.product_ranking import build_prompt, parse_response


# --------------------------------------------------------------------------- #
# Custom exceptions
# --------------------------------------------------------------------------- #

class RankingServiceError(Exception):
    """Base exception for the ranking service."""


class RateLimitExceeded(RankingServiceError):
    """Raised when the OpenAI rate limit is hit repeatedly after max retries."""


class InvalidModelOutput(RankingServiceError):
    """Raised when the model returns a response that cannot be parsed."""


# --------------------------------------------------------------------------- #
# Service class
# --------------------------------------------------------------------------- #

class RankingService:
    """
    Encapsulates GPT-assisted product ranking.

    Attributes:
        model: OpenAI model name to call (default ``gpt-4o``).
    """

    _SYSTEM_PROMPT = (
        "You are an expert ecommerce assistant who ranks products and "
        "explains the choices in a helpful, concise way."
    )

    def __init__(self, api_key: str | None = None, model: str = "gpt-4o"):
        resolved_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        if not resolved_key:
            raise ValueError(
                "OPENAI_API_KEY must be set either via the constructor or "
                "the OPENAI_API_KEY environment variable."
            )
        # openai >= 1.0 uses an explicit client instance.
        self._client = openai.OpenAI(api_key=resolved_key)
        self.model = model

    def rank_products(
        self,
        raw_products: list[dict[str, Any]],
        user_context: str = "",
        max_retries: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Return the top-3 products with reasoning and expert tips.

        Args:
            raw_products:  List of product dicts from SerpAPI (or similar).
                           Must contain at least the keys: title, price, rating.
                           Caller is responsible for ensuring at least 3 items.
            user_context:  Short description of the session or query used so
                           the model can personalise the explanations.
            max_retries:   Maximum number of retry attempts on rate-limit errors.

        Returns:
            List of exactly 3 dicts, each containing:
              title, price, rating, reason, expert_tip.

        Raises:
            RateLimitExceeded:  If the rate limit persists after max_retries.
            InvalidModelOutput: If the model response cannot be parsed as JSON.
        """
        prompt = build_prompt(raw_products, user_context)

        for attempt in range(max_retries):
            try:
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self._SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.6,
                )
                text = response.choices[0].message.content
                structured = parse_response(text)

                # Validate that we received exactly three items with all required keys.
                required_keys = {"title", "price", "rating", "reason", "expert_tip"}
                if not isinstance(structured, list) or len(structured) != 3:
                    raise InvalidModelOutput(
                        f"Expected 3 items, got {len(structured) if isinstance(structured, list) else type(structured)}"
                    )
                for item in structured:
                    missing = required_keys - set(item.keys())
                    if missing:
                        raise InvalidModelOutput(f"Missing required field(s): {missing}")

                return structured

            except openai.RateLimitError:
                # Exponential backoff with jitter before retrying.
                sleep_seconds = (2 ** attempt) + random.random()
                time.sleep(sleep_seconds)
                continue

            except ValueError as exc:
                # JSON parse failure from parse_response.
                raise InvalidModelOutput(str(exc)) from exc

        raise RateLimitExceeded(
            f"OpenAI rate limit persisted after {max_retries} attempts."
        )


# simple demonstration / standalone run
if __name__ == "__main__":
    # this block is intentionally minimal; real callers would be part of
    # a web service or other application.
    sample = [
        {"title": "Widget A", "price": 12.99, "rating": 4.3},
        {"title": "Widget B", "price": 15.50, "rating": 4.7},
        {"title": "Widget C", "price": 9.99, "rating": 4.0},
        {"title": "Widget D", "price": 20.00, "rating": 4.9},
    ]
    svc = RankingService()
    result = svc.rank_products(sample, user_context="looking for a budget-friendly phone")
    print(result)