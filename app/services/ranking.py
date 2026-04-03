"""
Ranking service — analyses all recommended products and picks the single
best match for the user based on their original query.

Flow:
1. Collect all products across every category.
2. Send them to the LLM with the user's original message as context.
3. LLM returns a ranked list + a clear "best pick" with a reason.
4. Return a RankingResult containing the best product and full ranked list.
"""

import json
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any

from app.core.exceptions import AllProvidersFailedError, ProviderError, ProviderUnavailableError
from app.core.logger import get_logger
# CRITICAL FIX: RankedProduct is now imported from your internal models!
from app.models.internal import Category, RankedProduct

# Initialize the logger for this module
logger = get_logger(__name__)


# ── OUTPUT CONTRACT ──────────────────────────────────────────────────────────

@dataclass # This decorator automatically generates boilerplate code like __init__ and __repr__ for the data structure.
class RankingResult: # This class holds the final output of the ranking step to be passed back to the recommender.
    """Full output of the ranking step."""
    best_product: Optional[RankedProduct] = None
    ranked_list: List[RankedProduct] = field(default_factory=list)
    provider_used: Optional[str] = None


# ── PROMPT BUILDER CLASS ─────────────────────────────────────────────────────

class RankingPromptBuilder: # This class is responsible for formatting data and building the exact messages for the LLM.
    """Handles the construction of the system prompt and user context for the LLM."""

    # The system prompt is stored as a class-level string variable
    _SYSTEM_PROMPT = """\
You are a personal shopping advisor. A user has described what they need, \
and you have a list of product options across several categories.

Your job:
1. Rank ALL products from best to worst match for THIS specific user.
2. Identify the single BEST product and write a short, personal explanation \
   of exactly why it is the top pick for this user's situation.

Return ONLY valid JSON — no markdown, no extra text.

JSON schema:
{
  "best_product": {
    "title": "<product title>",
    "category": "<category it belongs to>",
    "price": "<price string or null>",
    "url": "<url or null>",
    "image_url": "<image url or null>",
    "source": "<retailer or null>",
    "rating": <number or null>,
    "why_its_good": "<1 sentence — what makes this product generally good>",
    "why_best_for_you": "<2-3 sentences — why this is the perfect pick for THIS user based on their exact query>"
  },
  "ranked_list": [
    {
      "rank": 1,
      "title": "<product title>",
      "category": "<category>",
      "price": "<price or null>",
      "url": "<url or null>",
      "image_url": "<image url or null>",
      "source": "<retailer or null>",
      "rating": <number or null>,
      "why_its_good": "<1 sentence explanation>"
    }
  ]
}

Ranking rules:
- Prioritise products that match the user's stated budget, if mentioned.
- Prioritise products that match specific constraints (lightweight, beginner-friendly, etc.).
- Higher rating breaks ties.
- why_best_for_you must directly reference words or constraints from the user's query.
- Never invent prices, URLs, or ratings not present in the input data.
"""

    def build_messages(self, user_message: str, products_by_category: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """
        Takes the user's query and the formatted product list, and builds the message array.
        """
        # Convert the dictionary of products into a formatted JSON string for the LLM to read
        listings_text = json.dumps(products_by_category, ensure_ascii=False, indent=2)
        
        # Combine the user's request and the product data
        user_content = (
            f"User's request: \"{user_message}\"\n\n"
            f"Product options:\n{listings_text}"
        )
        
        # Return the standard message format expected by most LLM APIs
        return [
            {"role": "system", "content": self._SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]


# ── DATA PARSER CLASS ────────────────────────────────────────────────────────

class ResponseParser: # This class isolates the logic for cleaning and parsing the LLM's raw text response.
    """Cleans the raw LLM output and converts it into strict Pydantic model instances."""

    def _clean_json(self, raw: str) -> str:
        """Removes markdown formatting (like ```json) from the LLM response."""
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            # Rejoin the string, ignoring the first and last lines if they contain markdown backticks
            text = "\n".join(
                line for line in lines if not line.startswith("```")
            ).strip()
        return text

    def parse(self, raw: str) -> Tuple[Optional[RankedProduct], List[RankedProduct]]:
        """Parses the cleaned JSON string into our internal Python objects."""
        text = self._clean_json(raw)

        try:
            # Attempt to parse the text as a JSON dictionary
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            # If the LLM returned garbage, log it and return empty results safely
            logger.warning(f"Ranking JSON parse failed: {exc} — raw: {text[:200]}")
            return None, []

        best_pick = self._parse_best_product(data.get("best_product"))
        ranked_list = self._parse_ranked_list(data.get("ranked_list", []))

        # Ensure the list is sorted by rank before returning
        ranked_list.sort(key=lambda p: p.rank)
        
        return best_pick, ranked_list

    def _parse_best_product(self, bp_data: Optional[Dict[str, Any]]) -> Optional[RankedProduct]:
        """Helper method to construct the rank-1 best product."""
        if not bp_data or not bp_data.get("title"):
            return None
            
        # Instantiate the Pydantic model imported from internal.py
        return RankedProduct(
            rank=1,
            title=bp_data.get("title", ""),
            category=bp_data.get("category", ""),
            price=bp_data.get("price"),
            url=bp_data.get("url"),
            image_url=bp_data.get("image_url"),
            source=bp_data.get("source"),
            rating=float(bp_data["rating"]) if bp_data.get("rating") is not None else None,
            why_its_good=bp_data.get("why_its_good", ""),
            why_best_for_you=bp_data.get("why_best_for_you", ""),
        )

    def _parse_ranked_list(self, list_data: List[Dict[str, Any]]) -> List[RankedProduct]:
        """Helper method to construct the full list of ranked alternatives."""
        ranked: List[RankedProduct] = []
        for item in list_data:
            if not item.get("title"):
                continue  # Skip items that are missing a title
            try:
                # Append a new Pydantic model for each valid item
                ranked.append(
                    RankedProduct(
                        rank=int(item.get("rank", len(ranked) + 1)),
                        title=item.get("title", ""),
                        category=item.get("category", ""),
                        price=item.get("price"),
                        url=item.get("url"),
                        image_url=item.get("image_url"),
                        source=item.get("source"),
                        rating=float(item["rating"]) if item.get("rating") is not None else None,
                        why_its_good=item.get("why_its_good", ""),
                        # We intentionally do not populate why_best_for_you for general ranked items
                    )
                )
            except Exception as exc:
                logger.debug(f"Skipping malformed ranked item: {exc}")
        return ranked


# ── PROVIDER MANAGER CLASS ───────────────────────────────────────────────────

class LLMProviderManager: # This class encapsulates the fallback logic for trying different AI APIs.
    """Manages LLM API calls and automatically falls back to secondary providers if one fails."""

    async def call_provider(self, messages: List[Dict[str, str]]) -> Tuple[str, str]:
        """Try providers in order: Gemini → GROQ → OpenAI → Ollama."""
        errors: List[str] = []
        providers_to_try = []

        # Safely attempt to load each provider. If one isn't configured, we skip it.
        try:
            from app.providers.gemini_provider import GeminiProvider
            providers_to_try.append(GeminiProvider())
        except ProviderUnavailableError:
            pass

        try:
            from app.providers.groq_provider import GroqProvider
            providers_to_try.append(GroqProvider())
        except ProviderUnavailableError:
            pass

        try:
            from app.providers.openai_provider import OpenAIProvider
            providers_to_try.append(OpenAIProvider())
        except ProviderUnavailableError:
            pass

        try:
            from app.providers.ollama_provider import OllamaProvider
            providers_to_try.append(OllamaProvider())
        except ProviderUnavailableError:
            pass

        # If the list is empty, we have a major configuration problem
        if not providers_to_try:
            raise AllProvidersFailedError("No AI providers configured.")

        # Iterate through the available providers until one succeeds
        for provider in providers_to_try:
            try:
                # Call the LLM with a low temperature for more deterministic JSON output
                raw = await provider.complete(messages, temperature=0.2, max_tokens=2048)
                return raw, provider.name
            except (ProviderError, ProviderUnavailableError) as exc:
                # Record the error and loop to the next provider
                errors.append(f"{provider.name}: {exc}")
                logger.warning(f"Ranking: {provider.name} failed — trying next")

        # If the loop finishes without returning, every provider failed
        raise AllProvidersFailedError(
            "All providers failed during ranking.", detail="; ".join(errors)
        )


# ── MAIN ORCHESTRATOR CLASS ──────────────────────────────────────────────────

class RankingService: # This is the main service class that coordinates the builders, parsers, and managers.
    """The public API for the ranking module. Orchestrates the full ranking pipeline."""

    def __init__(self) -> None:
        """Instantiate the helper classes needed to run the pipeline."""
        self._prompt_builder = RankingPromptBuilder()
        self._parser = ResponseParser()
        self._provider_manager = LLMProviderManager()

    def _flatten_categories(self, categories: List[Category]) -> List[Dict[str, Any]]:
        """
        Converts internal Category objects into a flat list of dicts
        that the LLM can easily reason about.
        """
        flat: List[Dict[str, Any]] = []
        for cat in categories:
            for product in cat.products:
                flat.append({
                    "category": cat.name,
                    "title": product.title,
                    "price": product.price,
                    "url": product.url,
                    "image_url": product.image_url,
                    "source": product.source,
                    "rating": product.rating,
                    "explanation": product.explanation,
                })
        return flat

    async def rank_products(self, user_message: str, categories: List[Category]) -> RankingResult:
        """
        Rank all products across all categories and identify the single best
        product for the user based on their original query.
        """
        # Step 1: Flatten the internal models into simple dictionaries
        flat_products = self._flatten_categories(categories)

        # Early exit if there is nothing to rank
        if not flat_products:
            logger.warning("rank_products called with no products — skipping LLM call")
            return RankingResult()

        # Step 2: Group by category for cleaner LLM context
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for p in flat_products:
            grouped.setdefault(p["category"], []).append(p)

        products_by_category = [
            {"category": cat, "products": prods}
            for cat, prods in grouped.items()
        ]

        # Step 3: Build the system and user messages
        messages = self._prompt_builder.build_messages(user_message, products_by_category)

        # Step 4: Execute the LLM call via the Provider Manager
        try:
            raw, provider_used = await self._provider_manager.call_provider(messages)
            logger.info(f"Product ranking succeeded via {provider_used}")
        except AllProvidersFailedError as exc:
            logger.error(f"Ranking failed entirely: {exc}")
            return RankingResult()

        # Step 5: Parse the raw LLM output back into Python objects
        best, ranked_list = self._parser.parse(raw)

        # Step 6: Graceful fallback — if the LLM failed to identify a best pick, promote rank 1
        if not best and ranked_list:
            best = ranked_list[0]
            # Copy the generic explanation into the specific one so the UI doesn't break
            best.why_best_for_you = best.why_its_good

        # Step 7: Return the final assembled dataclass
        return RankingResult(
            best_product=best,
            ranked_list=ranked_list,
            provider_used=provider_used,
        )

# Optional: Provide a single module-level async function if backward compatibility is needed.
# Other files can just call `await rank_products(...)` which instantiates the class under the hood.
async def rank_products(user_message: str, categories: List[Category]) -> RankingResult:
    """Convenience function to instantiate the service and run the ranking."""
    service = RankingService()
    return await service.rank_products(user_message, categories)