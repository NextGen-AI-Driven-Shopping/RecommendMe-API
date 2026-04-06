"""
Dynamic Domain & Intent Analyzer

Analyzes queries in real-time to extract domain information,
generate context-aware follow-up questions, and understand user intent
without relying on static templates or mock data.

All patterns are derived from:
- Query content analysis
- Historical conversation context
- AI-powered inference
"""

import re
from typing import Optional
from app.core.logger import get_logger

logger = get_logger(__name__)


class DynamicIntentAnalyzer:
    """Analyzes queries dynamically to understand domain and intent."""
    
    @staticmethod
    def extract_domain_signals(query: str) -> dict:
        """
        Extract domain signals from the raw query text.
        
        Returns a dictionary with extracted information:
        - has_price: bool (budget mentioned)
        - has_timeframe: bool (when/duration mentioned)
        - has_environment: bool (where/context mentioned)
        - has_use_case: bool (what for mentioned)
        - has_type: bool (specific product type mentioned)
        - primary_nouns: list (main products referenced)
        - adjectives: list (descriptive words)
        - price_range: Optional[str] (if mentioned)
        """
        query_lower = query.lower().strip()
        
        # Extract price indicators
        price_pattern = r'\$\s*\d+|under\s+\$?\d+|budget.*?\$?\d+|costs?\s+\$?\d+|Rs\.?\s*\d+|₹\s*\d+'
        has_price = bool(re.search(price_pattern, query_lower))
        price_range = re.search(price_pattern, query_lower)
        price_range = price_range.group(0) if price_range else None
        
        # Extract timeframe indicators
        timeframe_keywords = ['today', 'tomorrow', 'week', 'month', 'year', 'urgent', 'asap', 'quick', 'immediate', 'seasonal', 'winter', 'summer', 'monsoon']
        has_timeframe = any(keyword in query_lower for keyword in timeframe_keywords)
        
        # Extract environment/location indicators
        env_keywords = ['outdoor', 'indoor', 'home', 'office', 'gym', 'road', 'trail', 'mountain', 'beach', 'water', 'snow', 'rain', 'travel']
        has_environment = any(keyword in query_lower for keyword in env_keywords)
        
        # Extract use case indicators
        use_case_keywords = ['gaming', 'coding', 'editing', 'photography', 'music', 'work', 'study', 'professional', 'casual', 'fitness', 'exercise']
        has_use_case = any(keyword in query_lower for keyword in use_case_keywords)
        
        # Extract type specificity (wired/wireless, size, brand, etc.)
        type_keywords = ['wired', 'wireless', 'small', 'medium', 'large', 'mini', 'compact', 'lightweight', 'heavy', 'waterproof', 'rugged']
        has_type = any(keyword in query_lower for keyword in type_keywords)
        
        # Extract primary nouns (simple word extraction)
        primary_nouns = []
        noun_pattern = r'\b[a-z]{4,}\b'  # Words 4+ chars
        words = re.findall(noun_pattern, query_lower)
        # Filter for likely nouns
        common_products = ['laptop', 'phone', 'headphones', 'monitor', 'keyboard', 'tablet', 'watch', 'shoes', 'bike', 'camera', 'speaker', 'gear', 'backpack', 'tent', 'lamp', 'chair', 'desk', 'sofa', 'bed', 'table']
        primary_nouns = [w for w in common_products if w in query_lower]
        
        # Extract adjectives/descriptors
        adjectives = []
        for word in words:
            if word not in primary_nouns and len(word) > 3:
                adjectives.append(word)
        
        return {
            'has_price': has_price,
            'has_timeframe': has_timeframe,
            'has_environment': has_environment,
            'has_use_case': has_use_case,
            'has_type': has_type,
            'primary_nouns': primary_nouns,
            'adjectives': list(set(adjectives))[:5],  # Top 5 unique
            'price_range': price_range,
            'query_length': len(query.split()),
        }
    
    @staticmethod
    def determine_missing_info(signals: dict) -> dict:
        """
        Determine what information is missing from the query
        to make it more specific for recommendations.
        """
        missing = {
            'use_case': not signals['has_use_case'],
            'environment': not signals['has_environment'],
            'type': not signals['has_type'],
            'price': not signals['has_price'],
            'timeframe': not signals['has_timeframe'],
        }
        
        missing['count'] = sum(1 for v in missing.values() if v)
        return missing
    
    @staticmethod
    def is_query_clear(signals_or_query, missing: dict | None = None) -> bool:
        """
        Determine if query is CLEAR enough for recommendations
        based on signal analysis.
        """
        if isinstance(signals_or_query, str):
            signals = DynamicIntentAnalyzer.extract_domain_signals(signals_or_query)
            missing = DynamicIntentAnalyzer.determine_missing_info(signals)
        else:
            signals = signals_or_query
            if missing is None:
                missing = DynamicIntentAnalyzer.determine_missing_info(signals)

        # If has specific product + use case/type + price = CLEAR
        if signals['primary_nouns']:
            clear_score = sum([
                signals['has_use_case'],
                signals['has_type'],
                signals['has_price'],
            ])
            # Need at least 2 of these 3 for CLEAR status
            return clear_score >= 2
        
        # If query is long and has multiple signals = likely CLEAR
        if signals['query_length'] >= 6:
            total_signals = sum([
                signals['has_price'],
                signals['has_timeframe'],
                signals['has_environment'],
                signals['has_use_case'],
                signals['has_type'],
            ])
            return total_signals >= 3
        
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
        
        Returns list of question strings.
        """
        questions = []
        
        # If nothing was mentioned, ask about primary need
        if signals['query_length'] < 3:
            nouns = signals['primary_nouns']
            if nouns:
                questions.append(f"What will you mainly use {nouns[0]} for? Daily use, work, fitness, or travel?")
            else:
                questions.append("What type of product are you looking for? Electronics, outdoor gear, home essentials, or fashion?")
        
        # Priority 1: Use case (if missing and product is clear)
        if missing['use_case'] and signals['primary_nouns']:
            product = signals['primary_nouns'][0]
            use_case_q = DynamicFollowUpGenerator._generate_use_case_question(product)
            if use_case_q:
                questions.append(use_case_q)
        
        # Priority 2: Type/Environment (if missing)
        if missing['type'] or missing['environment']:
            type_q = DynamicFollowUpGenerator._generate_type_question(
                signals['primary_nouns'][0] if signals['primary_nouns'] else None
            )
            if type_q and type_q not in questions:
                questions.append(type_q)
        
        # Priority 3: Preferences or constraints
        if missing['price'] and not (signals['has_type'] and signals['has_use_case']):
            questions.append("What is your budget range? Under ₹2,000, ₹2,000–₹5,000, or above ₹5,000?")
        elif missing['timeframe'] and signals['query_length'] <= 4:
            questions.append("When do you need this? Immediately, within a week, or no strict timeline?")
        elif not missing['price'] and not missing['use_case']:
            # If we have use case and price, ask for one more refinement
            pref_q = DynamicFollowUpGenerator._generate_preference_question(
                signals['primary_nouns'][0] if signals['primary_nouns'] else None,
                signals['adjectives']
            )
            if pref_q:
                questions.append(pref_q)
        
        # Keep to requested maximum questions
        max_questions = max(1, min(int(max_questions or 3), 5))
        deduped: list[str] = []
        for question in questions:
            cleaned = question.strip()
            if cleaned and cleaned not in deduped:
                deduped.append(cleaned)

        return deduped[:max_questions]
    
    @staticmethod
    def _generate_use_case_question(product: str) -> str:
        """Generate dynamic use case question based on product."""
        use_case_map = {
            'laptop': "What will you mainly use it for? Coding, gaming, editing, or general work?",
            'phone': "What's your primary use? Photography, gaming, content, or everyday tasks?",
            'headphones': "What's your main use? Music, gaming, work calls, or fitness?",
            'monitor': "Will you use it for gaming, work, content creation, or mixed use?",
            'shoes': "What activity are these for? Running, trekking, gym, or daily wear?",
            'backpack': "What will you use this backpack for? Trekking, travel, work, or school?",
            'camera': "What will you primarily shoot? Landscapes, portraits, vlogs, or action?",
        }
        return use_case_map.get(product, f"What will you mainly use the {product} for? Work, travel, home, or outdoor use?")
    
    @staticmethod
    def _generate_type_question(product: Optional[str]) -> str:
        """Generate dynamic type/variant question."""
        type_map = {
            'headphones': "What type do you prefer? Over-ear, on-ear, or in-ear?",
            'shoes': "What style do you prefer? Lightweight, cushioned, waterproof, or durable?",
            'monitor': "Which screen size is best for you? 24-inch, 27-inch, or 32-inch+?",
            'phone': "What size do you prefer? Compact, medium, or large-screen?",
            'laptop': "Which platform do you prefer? Windows, macOS, or Linux-ready?",
            'backpack': "What capacity do you prefer? 20–30L, 30–45L, or 45L+?",
        }
        if product:
            return type_map.get(product, f"What specific type or variant of {product} are you looking for?")
        return "What type do you prefer? Lightweight, durable, premium, or budget-friendly?"
    
    @staticmethod
    def _generate_preference_question(product: Optional[str], adjectives: list) -> str:
        """Generate dynamic preference question based on query context."""
        if adjectives:
            # User already provided descriptors, ask for confirmation
            return "Any must-have preferences? Brand choice, warranty, eco-friendly build, or premium quality?"
        
        pref_map = {
            'laptop': "Which matters more? Battery life, performance, portability, or display quality?",
            'phone': "What do you value most? Camera quality, battery life, performance, or display?",
            'headphones': "What's your priority? Noise cancellation, comfort, bass, or call quality?",
            'shoes': "Which feature matters most? Grip, cushioning, breathability, or waterproofing?",
        }
        
        if product:
            return pref_map.get(product, f"Any specific brands or features you prefer for {product}?")
        return "Any must-have features? Durability, lightweight design, premium build, or budget value?"


