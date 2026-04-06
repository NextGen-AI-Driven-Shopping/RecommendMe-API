# AI Model Pipeline

## Stage 1: Query Clarity

Service: `app/services/vagueness.py`

- Classifies input as `CLEAR` or `VAGUE`.
- For vague inputs, returns guided, option-rich follow-up questions.
- Clarification flow supports max 5 questions (3 initial + up to 2 additional).

Fallback tiers:

1. Groq models (max 4)
2. OpenAI models (max 4)
3. Gemini models (max 4)
4. Ollama local fallback

If all tiers fail, API returns an unavailable message.

## Stage 2: Category and Product Planning

Service: `app/services/recommender.py`

- Produces category list, reasoning summary, and planned product candidates.
- Uses the same tiered LLM fallback sequence with retries.

## Stage 3: Product Retrieval

Service: `app/routes/v1/query.py` + `app/services/products.py`

Per category:

- Fetch up to 10 items.
- Planned items are fetched individually (up to 10).
- Remaining planned items are fetched with grouped query fallback.
- Product retrieval source order:
	- SerpAPI Google Shopping first.
	- Direct Google fallback only when SerpAPI fails or returns empty.
- Progressive session snapshots are updated while each category/product is fetched.
- If no live listings can be built, fallback product cards with search links are returned.

## Ranking and Labels

- Rank label assigned as `Best Choice`, then `Top N`.
- Product explanation is included for recommendation transparency.
