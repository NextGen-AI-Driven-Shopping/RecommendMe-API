"""
Dynamic Domain & Intent Analyzer

Analyzes queries in real-time to extract domain information,
generate context-aware follow-up questions, and understand user intent
without relying on static templates or mock data.

Now fully domain-agnostic: handles shopping products, movies, software,
travel, food, services, and any other topic the user might ask about.
"""

import re
from typing import Optional
from app.core.logger import get_logger

logger = get_logger(__name__)


class DynamicIntentAnalyzer:
    """Analyzes queries dynamically to understand domain and intent."""

    # ── Domain signal tables ─────────────────────────────────────────────

    _ENTERTAINMENT_KEYWORDS = {
        "movie", "movies", "film", "films", "show", "shows", "series",
        "anime", "documentary", "watch", "streaming", "netflix", "prime",
        "hulu", "hotstar", "disney", "book", "books", "novel", "novels",
        "read", "reading", "album", "music", "song", "songs", "playlist",
        "podcast", "game", "games", "videogame", "gaming", "play",
        "thriller", "horror", "comedy", "romance", "drama", "action",
        "fantasy", "sci-fi",
    }

    _SOFTWARE_KEYWORDS = {
        "tool", "tools", "app", "apps", "software", "platform", "saas",
        "crm", "erp", "ide", "editor", "framework", "library", "api",
        "plugin", "extension", "dashboard", "analytics", "automation",
        "workflow", "productivity", "collaboration", "database", "hosting",
        "cloud", "devops", "monitoring", "design", "figma", "notion",
        "jira", "slack", "asana", "webflow", "wordpress", "cms",
    }

    _TRAVEL_KEYWORDS = {
        "travel", "trip", "vacation", "holiday", "tour", "destination",
        "hotel", "resort", "hostel", "flight", "airline", "itinerary",
        "sightseeing", "visit", "backpacking", "luggage", "passport",
        "visa", "road trip",
    }

    _FOOD_KEYWORDS = {
        "recipe", "recipes", "cook", "cooking", "bake", "baking",
        "cuisine", "restaurant", "food", "dish", "meal", "breakfast",
        "lunch", "dinner", "snack", "ingredient", "diet", "vegan",
        "vegetarian", "keto", "dessert", "coffee", "tea", "smoothie",
    }

    _SHOPPING_KEYWORDS = {
        "laptop", "phone", "headphones", "shoes", "bag", "backpack",
        "camera", "monitor", "keyboard", "mouse", "tablet", "watch",
        "earbuds", "speaker", "tv", "television", "refrigerator",
        "washing machine", "microwave", "furniture", "chair", "desk",
        "sofa", "bed", "mattress", "clothing", "shirt", "jeans", "jacket",
        "dress", "sneakers", "sunglasses", "helmet", "cycle", "bicycle",
        "scooter", "gear", "equipment", "kit", "setup", "build", "pan",
        "pans", "pot", "pots", "knife", "knives", "stove", "induction",
        "mixer", "printer", "router", "charger",
    }

    # ── Question templates per domain ─────────────────────────────────────

    _USE_CASE_TEMPLATES: dict[str, str] = {
        # Shopping items
        "laptop":      "What will you mainly use it for? Coding, gaming, video editing, or general use?",
        "phone":       "What's your primary use? Photography, gaming, content, or everyday tasks?",
        "headphones":  "What's your main use? Music, gaming, work calls, or fitness?",
        "monitor":     "Will you use it for gaming, work, content creation, or mixed use?",
        "shoes":       "What activity are these for? Running, trekking, gym, or daily wear?",
        "backpack":    "What will you use this backpack for? Trekking, travel, work, or school?",
        "camera":      "What will you primarily shoot? Landscapes, portraits, vlogs, or action?",
        # Entertainment
        "movie":       "What mood are you in — something light, intense, emotional, or funny?",
        "movies":      "What mood are you in — something light, intense, emotional, or funny?",
        "show":        "Genre preference — drama, comedy, thriller, sci-fi, or documentary?",
        "shows":       "Genre preference — drama, comedy, thriller, sci-fi, or documentary?",
        "book":        "What genre do you enjoy — fiction, non-fiction, self-help, thriller, or fantasy?",
        "books":       "What genre do you enjoy — fiction, non-fiction, self-help, thriller, or fantasy?",
        "game":        "Platform preference — PC, console, mobile? And genre — action, RPG, strategy, puzzle?",
        "games":       "Platform preference — PC, console, mobile? And genre — action, RPG, strategy, puzzle?",
        # Software
        "tool":        "What will you use it for — solo work, team collaboration, or client management?",
        "tools":       "What will you use it for — solo work, team collaboration, or client management?",
        "software":    "Individual or team use? And what's the primary workflow — project management, analytics, or communication?",
        "app":         "Mobile or desktop? And what's the core task it needs to do?",
        # Travel
        "travel":      "Leisure, adventure, or business trip? Solo, couple, or group?",
        "trip":        "Day trip, weekend getaway, or longer vacation? Solo or with others?",
        "hotel":       "Business or leisure stay? Budget range and preferred amenities?",
        # Food
        "recipe":      "Cuisine preference — Italian, Indian, Asian, or something else? Any dietary restrictions?",
        "recipes":     "Cuisine preference — Italian, Indian, Asian, or something else? Any dietary restrictions?",
        "restaurant":  "Cuisine type and occasion — casual dinner, date night, or family outing?",
    }

    _TYPE_TEMPLATES: dict[str, str] = {
        "headphones":  "What type do you prefer? Over-ear, on-ear, or in-ear?",
        "shoes":       "Style preference? Lightweight, cushioned, waterproof, or durable?",
        "monitor":     "Which screen size? 24-inch, 27-inch, or 32-inch+?",
        "phone":       "Screen size preference? Compact, standard, or large?",
        "laptop":      "Platform preference? Windows, macOS, or Linux-ready?",
        "backpack":    "Capacity preference? 20–30L, 30–45L, or 45L+?",
        "movie":       "Any format preference — theatres, streaming, or either?",
        "movies":      "Any format preference — theatres, streaming, or either?",
    }

    _PREFERENCE_TEMPLATES: dict[str, str] = {
        "laptop":      "Which matters more to you? Battery life, performance, portability, or display quality?",
        "phone":       "What do you value most? Camera quality, battery life, performance, or display?",
        "headphones":  "Priority? Noise cancellation, comfort, bass quality, or call clarity?",
        "shoes":       "Most important feature? Grip, cushioning, breathability, or waterproofing?",
        "movie":       "Any specific director or actor you enjoy watching?",
        "movies":      "Any specific director or actor you enjoy watching?",
        "book":        "Any author preferences, or are you open to any recommendation?",
        "tool":        "Must-have feature — free tier, integrations, mobile app, or offline support?",
        "software":    "Priority — ease of use, customization depth, integration options, or price?",
    }

    @staticmethod
    def _detect_domain(query_lower: str) -> str:
        """Infer the domain from keyword presence."""
        # Entertainment signals take strong precedence for media queries
        ent_count = sum(1 for kw in DynamicIntentAnalyzer._ENTERTAINMENT_KEYWORDS if kw in query_lower)
        sw_count = sum(1 for kw in DynamicIntentAnalyzer._SOFTWARE_KEYWORDS if kw in query_lower)
        travel_count = sum(1 for kw in DynamicIntentAnalyzer._TRAVEL_KEYWORDS if kw in query_lower)
        food_count = sum(1 for kw in DynamicIntentAnalyzer._FOOD_KEYWORDS if kw in query_lower)
        shop_count = sum(1 for kw in DynamicIntentAnalyzer._SHOPPING_KEYWORDS if kw in query_lower)

        scores = {
            "entertainment": ent_count,
            "software": sw_count,
            "travel": travel_count,
            "food": food_count,
            "shopping": shop_count,
        }
        best = max(scores, key=lambda k: scores[k])
        return best if scores[best] > 0 else "general"

    @staticmethod
    def _detect_primary_subject(query_lower: str) -> list[str]:
        """
        Detect the primary subject(s) of the query.
        Works for both physical products and non-product domains.
        """
        candidates: list[str] = []

        # Build combined keyword universe
        all_keywords = (
            DynamicIntentAnalyzer._SHOPPING_KEYWORDS
            | DynamicIntentAnalyzer._ENTERTAINMENT_KEYWORDS
            | DynamicIntentAnalyzer._SOFTWARE_KEYWORDS
            | DynamicIntentAnalyzer._TRAVEL_KEYWORDS
            | DynamicIntentAnalyzer._FOOD_KEYWORDS
        )

        for kw in all_keywords:
            if kw in query_lower:
                candidates.append(kw)

        # Sort by length (more specific terms first)
        candidates.sort(key=len, reverse=True)
        # Deduplicate: remove substrings of already found terms
        deduped: list[str] = []
        for c in candidates:
            if not any(c in d and c != d for d in deduped):
                deduped.append(c)

        return deduped[:3]

    @staticmethod
    def extract_domain_signals(query: str) -> dict:
        """
        Extract domain signals from the raw query text.

        Returns a dictionary with extracted information across all domains
        (shopping, entertainment, software, travel, food, general).
        """
        query_lower = query.lower().strip()

        # Price / budget signals
        price_pattern = r'\$\s*\d+|under\s+\$?\d+|budget.*?\$?\d+|costs?\s+\$?\d+|Rs\.?\s*\d+|₹\s*\d+'
        has_price = bool(re.search(price_pattern, query_lower))
        price_range_match = re.search(price_pattern, query_lower)
        price_range = price_range_match.group(0) if price_range_match else None

        # Timeframe / urgency signals
        timeframe_keywords = [
            'today', 'tonight', 'tomorrow', 'this week', 'this month',
            'week', 'month', 'year', 'urgent', 'asap', 'quick', 'immediate',
            'seasonal', 'winter', 'summer', 'monsoon',
        ]
        has_timeframe = any(kw in query_lower for kw in timeframe_keywords)

        # Environment / context signals  
        env_keywords = [
            'outdoor', 'indoor', 'home', 'office', 'gym', 'road', 'trail',
            'mountain', 'beach', 'water', 'snow', 'rain', 'travel', 'alone',
            'solo', 'group', 'family', 'couple', 'team', 'remote',
        ]
        has_environment = any(kw in query_lower for kw in env_keywords)

        # Use case signals (broader than before — includes non-shopping)
        use_case_keywords = [
            # Shopping use cases
            'gaming', 'coding', 'editing', 'photography', 'music', 'work',
            'study', 'professional', 'casual', 'fitness', 'exercise',
            'cooking', 'baking', 'kitchen',
            # Entertainment use cases
            'watching', 'reading', 'listening', 'playing',
            # Software use cases
            'collaboration', 'automation', 'analytics', 'design',
            'project management', 'communication',
            # Mood-based (movies/books)
            'light', 'intense', 'funny', 'emotional', 'relaxing',
            'inspirational', 'exciting',
        ]
        has_use_case = any(kw in query_lower for kw in use_case_keywords)

        # Type / constraint signals
        type_keywords = [
            'wired', 'wireless', 'small', 'medium', 'large', 'mini',
            'compact', 'lightweight', 'heavy', 'waterproof', 'rugged',
            'free', 'paid', 'open source', 'cloud-based', 'mobile',
            'beginner', 'advanced', 'expert',
        ]
        has_type = any(kw in query_lower for kw in type_keywords)

        # Detect domain
        domain = DynamicIntentAnalyzer._detect_domain(query_lower)

        # Detect primary subject(s)
        primary_nouns = DynamicIntentAnalyzer._detect_primary_subject(query_lower)

        # Extract adjectives (non-keyword descriptors)
        word_pattern = r'\b[a-z]{4,}\b'
        words = re.findall(word_pattern, query_lower)
        all_subjects = set(primary_nouns)
        adjectives = [w for w in words if w not in all_subjects and len(w) > 3]

        return {
            'has_price': has_price,
            'has_timeframe': has_timeframe,
            'has_environment': has_environment,
            'has_use_case': has_use_case,
            'has_type': has_type,
            'primary_nouns': primary_nouns,
            'adjectives': list(set(adjectives))[:5],
            'price_range': price_range,
            'query_length': len(query.split()),
            'domain': domain,
        }

    @staticmethod
    def determine_missing_info(signals: dict) -> dict:
        """
        Determine what context is missing from the query.
        Domain-adaptive: different fields matter for different domains.
        """
        domain = signals.get('domain', 'general')

        missing: dict = {}

        if domain == 'entertainment':
            # For entertainment, mood/genre matters more than price
            missing['mood_genre'] = not signals['has_use_case'] and not signals['has_type']
            missing['platform'] = not signals['has_environment']
            missing['companion_context'] = not signals['has_timeframe']
            missing['price'] = False  # Price rarely matters for free content
        elif domain == 'software':
            missing['use_case'] = not signals['has_use_case']
            missing['team_size'] = not signals['has_environment']
            missing['type'] = not signals['has_type']
            missing['price'] = not signals['has_price']
            missing['timeframe'] = False
        elif domain == 'travel':
            missing['use_case'] = not signals['has_use_case']  # trip_type
            missing['environment'] = not signals['has_environment']
            missing['type'] = not signals['has_type']  # solo/group
            missing['price'] = not signals['has_price']
            missing['timeframe'] = not signals['has_timeframe']
        elif domain == 'food':
            missing['use_case'] = not signals['has_use_case']  # dietary pref
            missing['environment'] = not signals['has_environment']  # occasion
            missing['type'] = not signals['has_type']  # cuisine type
            missing['price'] = not signals['has_price']
            missing['timeframe'] = False
        else:
            # Shopping / general (original logic, preserved)
            missing['use_case'] = not signals['has_use_case']
            missing['environment'] = not signals['has_environment']
            missing['type'] = not signals['has_type']
            missing['price'] = not signals['has_price']
            missing['timeframe'] = not signals['has_timeframe']

        missing['count'] = sum(1 for v in missing.values() if isinstance(v, bool) and v)
        return missing

    @staticmethod
    def is_query_clear(signals_or_query, missing: dict | None = None) -> bool:
        """
        Determine if query is CLEAR enough for recommendations.
        Domain-adaptive clarity scoring.
        """
        if isinstance(signals_or_query, str):
            signals = DynamicIntentAnalyzer.extract_domain_signals(signals_or_query)
            missing = DynamicIntentAnalyzer.determine_missing_info(signals)
        else:
            signals = signals_or_query
            if missing is None:
                missing = DynamicIntentAnalyzer.determine_missing_info(signals)

        domain = signals.get('domain', 'general')

        # Very long queries with multiple signals are likely CLEAR
        if signals['query_length'] >= 7:
            total_signals = sum([
                signals['has_price'],
                signals['has_timeframe'],
                signals['has_environment'],
                signals['has_use_case'],
                signals['has_type'],
            ])
            if total_signals >= 2:
                return True

        if domain == 'entertainment':
            # Clear if mood/genre is known
            return signals['has_use_case'] or signals['has_type']

        if domain == 'software':
            # Clear if use case is known
            return signals['has_use_case']

        if domain in ('travel', 'food'):
            # Clear if use case/context is known
            return signals['has_use_case'] and (signals['has_type'] or signals['has_environment'])

        # Shopping / general: need product + at least 2 constraints
        if signals['primary_nouns']:
            clear_score = sum([
                signals['has_use_case'],
                signals['has_type'],
                signals['has_price'],
            ])
            return clear_score >= 2

        return False


class DynamicFollowUpGenerator:
    """Generates context-aware follow-up questions based on actual query analysis."""

    @staticmethod
    def generate_from_signals(
        query: str,
        signals: dict,
        missing: dict,
        max_questions: int = 3,
    ) -> list[str]:
        """
        Generate up to 3 contextual follow-up questions based on
        what information is missing and what the query reveals.

        Fully domain-agnostic.
        """
        questions: list[str] = []
        domain = signals.get('domain', 'general')
        primary = signals['primary_nouns']
        subject = primary[0] if primary else None

        # If query is very short with no clear subject, ask about the domain
        if signals['query_length'] < 3 or not subject:
            if domain == 'entertainment':
                questions.append("What are you in the mood for — a movie, show, book, music, or a game?")
            elif domain == 'software':
                questions.append("What type of tool are you looking for — productivity, analytics, communication, or design?")
            elif domain == 'travel':
                questions.append("Are you planning a domestic or international trip? And how long?")
            elif domain == 'food':
                questions.append("Looking for a recipe to cook, or a restaurant recommendation?")
            else:
                questions.append("What type of product or service are you looking for? Electronics, outdoor gear, software, or something else?")

        # Primary question: use-case / mood / intent
        if subject:
            use_case_q = DynamicIntentAnalyzer._USE_CASE_TEMPLATES.get(subject)
            if not use_case_q:
                if domain == 'entertainment':
                    use_case_q = f"What mood or genre suits you for {subject} right now?"
                elif domain == 'software':
                    use_case_q = f"What will you primarily use {subject} for — solo, team, or client work?"
                elif domain == 'travel':
                    use_case_q = f"What's the purpose of this {subject} — leisure, adventure, or business?"
                elif domain == 'food':
                    use_case_q = f"Any cuisine preference or dietary requirements for {subject}?"
                else:
                    use_case_q = f"What will you mainly use {subject} for? Work, travel, home, or outdoor?"
            if use_case_q and use_case_q not in questions:
                questions.append(use_case_q)

        # Secondary question: type / constraint / platform
        if missing.get('type') or missing.get('platform') or missing.get('team_size'):
            type_q = DynamicIntentAnalyzer._TYPE_TEMPLATES.get(subject or "")
            if not type_q:
                if domain == 'entertainment':
                    type_q = "Any platform preference — Netflix, Prime, theatre, or happy with any?"
                elif domain == 'software':
                    type_q = "Individual use or for a team? And what size is the team?"
                elif domain == 'shopping':
                    type_q = f"Any specific type or variant in mind for {subject}?" if subject else "Any size, form factor, or type preference?"
                # food/travel already covered by use_case question
            if type_q and type_q not in questions:
                questions.append(type_q)

        # Tertiary question: price / feature priority / constraints
        if domain in ('shopping', 'travel') and missing.get('price', True):
            questions.append("What's your budget range? Feel free to give a rough figure or range.")
        elif domain not in ('entertainment',):
            # Preference question for non-entertainment domains
            pref_q = DynamicIntentAnalyzer._PREFERENCE_TEMPLATES.get(subject or "")
            if pref_q and pref_q not in questions:
                questions.append(pref_q)

        # Deduplicate and limit
        max_questions = max(1, min(int(max_questions or 3), 5))
        deduped: list[str] = []
        for question in questions:
            cleaned = question.strip()
            if cleaned and cleaned not in deduped:
                deduped.append(cleaned)

        return deduped[:max_questions]
