"""
Intent Engine — domain-agnostic query classifier.

Classifies any user query into a domain (shopping, entertainment, software,
travel, food, general) and an intent (recommendation, comparison, exploration).

This is a lightweight, purely local module with no AI calls — it is used as
fast pre-processing before the vagueness check so that downstream prompts and
scoring can adapt to the detected domain.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from app.core.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

DomainType = Literal[
    "shopping",       # Physical/digital products to purchase
    "entertainment",  # Movies, shows, books, music, games
    "software",       # SaaS, apps, developer tools, platforms
    "travel",         # Destinations, hotels, transport
    "food",           # Restaurants, recipes, ingredients
    "services",       # Service providers, professionals
    "general",        # Catch-all
]

IntentType = Literal[
    "recommendation",  # User wants suggestions
    "comparison",      # User wants to compare options
    "exploration",     # User is browsing / researching
]


# ---------------------------------------------------------------------------
# Domain signal tables
# ---------------------------------------------------------------------------

_ENTERTAINMENT_SIGNALS = {
    "movie", "movies", "film", "films", "show", "shows", "series", "anime",
    "documentary", "watch", "streaming", "netflix", "amazon prime", "hulu",
    "disney", "hotstar", "thriller", "horror", "comedy", "romance", "drama",
    "action", "sci-fi", "fantasy", "anime", "manga", "book", "books", "novel",
    "novels", "read", "reading", "album", "music", "song", "songs", "playlist",
    "podcast", "game", "games", "videogame", "gaming", "play", "board game",
}

_SOFTWARE_SIGNALS = {
    "tool", "tools", "app", "apps", "software", "platform", "saas", "crm",
    "erp", "ide", "editor", "code editor", "framework", "library", "api",
    "plugin", "extension", "dashboard", "analytics", "automation", "workflow",
    "project management", "task manager", "productivity", "collaboration",
    "database", "hosting", "cloud", "devops", "ci/cd", "monitoring", "logging",
    "design tool", "ui ux", "figma", "notion", "jira", "slack", "asana",
    "webflow", "wordpress", "cms", "ecommerce platform",
}

_TRAVEL_SIGNALS = {
    "travel", "trip", "vacation", "holiday", "tour", "destination", "hotel",
    "resort", "hostel", "flight", "airline", "train", "bus", "road trip",
    "itinerary", "sightseeing", "visit", "country", "city", "beach", "mountain",
    "trek", "trekking", "hike", "hiking", "camping", "backpacking abroad",
    "visa", "passport", "luggage", "packing list",
}

_FOOD_SIGNALS = {
    "recipe", "recipes", "cook", "cooking", "bake", "baking", "cuisine",
    "restaurant", "food", "dish", "meal", "breakfast", "lunch", "dinner",
    "snack", "ingredient", "ingredients", "diet", "keto", "vegan", "vegetarian",
    "healthy food", "junk food", "dessert", "cake", "pizza", "salad",
    "coffee", "tea", "smoothie", "juice",
}

_SERVICES_SIGNALS = {
    "service", "services", "professional", "freelancer", "agency", "consultant",
    "lawyer", "doctor", "mechanic", "plumber", "electrician", "dentist",
    "therapist", "coach", "tutor", "instructor", "trainer", "catering",
    "cleaning", "delivery", "repair", "maintenance",
}

_SHOPPING_SIGNALS = {
    "buy", "purchase", "order", "shop", "price", "budget", "cost",
    "laptop", "phone", "headphones", "shoes", "bag", "backpack", "camera",
    "monitor", "keyboard", "mouse", "tablet", "watch", "earbuds", "speaker",
    "tv", "television", "refrigerator", "washing machine", "microwave",
    "furniture", "chair", "desk", "sofa", "bed", "mattress",
    "clothing", "shirt", "jeans", "jacket", "dress", "sneakers",
    "sunglasses", "helmet", "cycle", "bicycle", "scooter",
    "gear", "equipment", "kit", "setup", "build", "product", "products",
    "brand", "review", "comparison", "vs", "recommend",
}

_INTENT_RECOMMENDATION = {
    "recommend", "suggest", "best", "top", "good", "great", "should i",
    "help me find", "looking for", "need", "want", "find me", "which",
    "advice", "advise", "guide", "guide me",
}

_INTENT_COMPARISON = {
    "vs", "versus", "compare", "comparison", "difference between",
    "better", "worse", "pros and cons", "or", "which is better",
}

_INTENT_EXPLORATION = {
    "what are", "what is", "tell me about", "explain", "how does",
    "options", "alternatives", "types of", "kinds of", "overview",
}


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


@dataclass
class IntentResult:
    """Result of intent + domain classification for a user query."""

    domain: DomainType
    intent: IntentType
    confidence: float = 1.0
    signals_found: list[str] = field(default_factory=list)

    def is_product_domain(self) -> bool:
        """True when domain likely involves purchasable physical/digital products."""
        return self.domain in ("shopping",)

    def is_non_purchase_domain(self) -> bool:
        """True when SERP product search is NOT appropriate (e.g., movies, software reviews)."""
        return self.domain in ("entertainment", "software", "services", "general")

    def requires_price_context(self) -> bool:
        """True when price/budget is a meaningful signal for sufficiency scoring."""
        return self.domain in ("shopping", "travel", "food")

    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "intent": self.intent,
            "confidence": self.confidence,
        }


def _count_signal_matches(text: str, signals: set[str]) -> tuple[int, list[str]]:
    """Count how many signal phrases appear in the text, return (count, matched list)."""
    matched: list[str] = []
    for signal in signals:
        if signal in text:
            matched.append(signal)
    return len(matched), matched


def classify_intent(query: str) -> IntentResult:
    """
    Classify the domain and intent of a user query without any AI call.

    This is a fast, purely local classifier that uses keyword/phrase signals.
    It is intentionally conservative — it defaults to "general" and "recommendation"
    when uncertain rather than misclassifying.

    Args:
        query: Raw user query string.

    Returns:
        IntentResult with domain, intent, and confidence.
    """
    if not query or not query.strip():
        return IntentResult(domain="general", intent="recommendation")

    text = query.lower().strip()
    # Remove punctuation for easier matching
    text_clean = re.sub(r"[^\w\s]", " ", text)
    text_clean = re.sub(r"\s+", " ", text_clean).strip()

    # ── Domain scoring ─────────────────────────────────────────────────────
    domain_scores: dict[str, tuple[int, list[str]]] = {
        "entertainment": _count_signal_matches(text_clean, _ENTERTAINMENT_SIGNALS),
        "software":      _count_signal_matches(text_clean, _SOFTWARE_SIGNALS),
        "travel":        _count_signal_matches(text_clean, _TRAVEL_SIGNALS),
        "food":          _count_signal_matches(text_clean, _FOOD_SIGNALS),
        "services":      _count_signal_matches(text_clean, _SERVICES_SIGNALS),
        "shopping":      _count_signal_matches(text_clean, _SHOPPING_SIGNALS),
    }

    # Pick domain with highest signal count
    best_domain: DomainType = "general"
    best_count = 0
    best_signals: list[str] = []
    for domain, (count, signals_matched) in domain_scores.items():
        if count > best_count:
            best_count = count
            best_domain = domain  # type: ignore[assignment]
            best_signals = signals_matched

    # ── Intent scoring ─────────────────────────────────────────────────────
    cmp_count, _ = _count_signal_matches(text_clean, _INTENT_COMPARISON)
    rec_count, _ = _count_signal_matches(text_clean, _INTENT_RECOMMENDATION)
    exp_count, _ = _count_signal_matches(text_clean, _INTENT_EXPLORATION)

    if cmp_count >= 1:
        best_intent: IntentType = "comparison"
    elif exp_count > rec_count:
        best_intent = "exploration"
    else:
        best_intent = "recommendation"

    # ── Confidence ─────────────────────────────────────────────────────────
    # Low confidence if very few signals were found for the selected domain
    confidence = 1.0 if best_count >= 2 else (0.7 if best_count == 1 else 0.5)

    result = IntentResult(
        domain=best_domain,
        intent=best_intent,
        confidence=confidence,
        signals_found=best_signals[:5],
    )

    logger.debug(
        "intent_engine query=%r → domain=%s intent=%s confidence=%.2f signals=%s",
        query[:60],
        result.domain,
        result.intent,
        result.confidence,
        result.signals_found,
    )

    return result
