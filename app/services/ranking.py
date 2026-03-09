"""
Product ranking service.

Uses GPT-4o to sort the raw product results returned by SerpAPI
by relevance to the user's query and generates a concise natural-language
explanation for each recommendation.
"""

from app.models.responses import ProductCard


async def rank_products(
    products: list[ProductCard],
    query: str,
) -> list[ProductCard]:
    """
    Rank products by relevance and attach AI-generated explanations.

    Args:
        products: Un-ranked list of ProductCard objects from SerpAPI.
        query:    The original user query used as a relevance baseline.

    Returns:
        Products sorted from most to least relevant, each with an
        explanation field populated by GPT-4o.
    """
    # TODO: call GPT-4o with the ranking prompt and merge explanations
    pass
