import os
import time
import random
from typing import Any, Dict, List, Optional

import openai

from app.prompts.product_ranking import build_prompt, parse_response


class RankingServiceError(Exception):
    """Base exception for the ranking service."""


class RateLimitExceeded(RankingServiceError):
    """Raised when the OpenAI rate limit is hit repeatedly."""


class InvalidModelOutput(RankingServiceError):
    """Raised when the model returns something that cannot be parsed."""


class RankingService:
    """Encapsulates the logic for taking raw search results and
    producing a structured, GPT-assisted ranking.

    Attributes:
        model: the name of the OpenAI model to call (default ``gpt-4o``).
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o"):
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ValueError("OPENAI_API_KEY must be set")
        openai.api_key = key
        self.model = model

    def rank_products(
        self,
        raw_products: List[Dict[str, Any]],
        user_context: str = "",
        max_retries: int = 5,
    ) -> List[Dict[str, Any]]:
        """Return the top‑3 products with reasoning and tips.

        ``raw_products`` is the list of results returned from some
        upstream search (SerpAPI, etc).  It is the responsibility of the
        caller to ensure the list contains at least three entries.

        ``user_context`` should briefly describe the current session or
        query so that the model can craft personalised explanations.

        Raises
        ------
        RateLimitExceeded
            if the model continues to return rate limit errors after
            ``max_retries`` attempts.
        InvalidModelOutput
            if the model fails to produce parseable JSON.
        """

        prompt = build_prompt(raw_products, user_context)

        # simple exponential backoff loop
        for attempt in range(max_retries):
            try:
                resp = openai.ChatCompletion.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are an expert ecommerce assistant who ranks "
                                "products and explains the choices."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.6,
                )
                text = resp.choices[0].message.content
                structured = parse_response(text)
                # validate that we got exactly three items and required keys
                if not isinstance(structured, list) or len(structured) != 3:
                    raise InvalidModelOutput("expected three items")
                for item in structured:
                    if not all(k in item for k in ["title", "price", "rating", "reason", "expert_tip"]):
                        raise InvalidModelOutput("missing required field")
                return structured
            except openai.error.RateLimitError:
                # wait an exponentially increasing amount of time
                sleep = (2 ** attempt) + random.random()
                time.sleep(sleep)
                continue
            except ValueError as ve:
                # JSON parsing failure
                raise InvalidModelOutput(str(ve))

        raise RateLimitExceeded("took too many retries")


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