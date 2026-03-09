"""
Developer utility: generate mock SerpAPI responses for offline development.

Usage:
    python scripts/mock_serp.py --query "wireless headphones" --count 5

Outputs a JSON array of mock product objects to stdout.
Pipe to a file to create static fixtures:
    python scripts/mock_serp.py --query "laptop" --count 10 > tests/fixtures/mock_products.json
"""

import argparse
import json
import random

_MOCK_SOURCES = ["Amazon", "BestBuy", "Walmart", "NewEgg", "Target", "B&H Photo"]


def _generate_mock_product(index: int, query: str) -> dict:
    """Generate a single plausible mock product entry."""
    price = random.randint(20, 800)
    rating = round(random.uniform(3.5, 5.0), 1)
    return {
        "title": f"{query.title()} — Option {index + 1}",
        "price": f"${price}",
        "url": f"https://example.com/products/{index + 1}",
        "image_url": f"https://via.placeholder.com/300x300?text=Product+{index + 1}",
        "source": random.choice(_MOCK_SOURCES),
        "rating": rating,
        "explanation": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate mock SerpAPI product responses.")
    parser.add_argument("--query", type=str, default="product", help="Search query string.")
    parser.add_argument("--count", type=int, default=5, help="Number of mock products to generate.")
    args = parser.parse_args()

    products = [_generate_mock_product(i, args.query) for i in range(args.count)]
    print(json.dumps(products, indent=2))


if __name__ == "__main__":
    main()
