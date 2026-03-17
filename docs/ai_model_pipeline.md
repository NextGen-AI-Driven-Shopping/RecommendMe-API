# AI Model Pipeline

## Overview

The AI pipeline has two decision stages:

1. Vagueness detection.
2. Category and product reasoning.

## Stage 1: Vagueness Detection

Primary provider:

- Ollama (`app/services/vagueness.py`)

Behavior:

- If query is `VAGUE`, API returns clarification prompts.
- If query is `CLEAR`, API proceeds to category reasoning.

Fallback:

- OpenAI mini model fallback is used internally in vagueness service when Ollama fails.

## Stage 2: Category and Product Reasoning

Service:

- `app/services/recommender.py`

Provider chain:

1. Gemini
2. GROQ
3. OpenAI
4. Ollama

Expected normalized output schema:

```json
{
  "categories": ["category name"],
  "reasoning": "why these categories/products fit",
  "recommended_products": ["product type name"]
}
```

If all providers fail:

- API raises `AIServiceException` and returns `503`.

## Failure Conditions Triggering Fallback

- API/network error
- request timeout
- invalid JSON output
- invalid output schema
- missing provider credentials

## Product Enrichment

After category reasoning:

- API tries SerpAPI product fetch per category.
- If SerpAPI is unavailable, API returns local product placeholders derived from AI recommendations.
