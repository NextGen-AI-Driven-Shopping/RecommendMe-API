# RecommendMe API

FastAPI backend for AI-powered product recommendations with a provider-resilient reasoning pipeline.

## Project Overview

RecommendMe API receives a user shopping query, determines whether it is actionable, and either:

- returns follow-up clarification prompts, or
- returns category-based product recommendations.

The backend is designed for frontend apps and service consumers that need structured output and stable behavior even when individual AI providers fail.

## Architecture

Core layers:

- API routes: input parsing, response contracts, orchestration entrypoint.
- Services: vagueness detection, category reasoning, product fetch.
- Providers: Gemini, GROQ, OpenAI, Ollama via a shared abstraction.
- Prompts: isolated prompt templates for each AI decision step.
- Models: request/response and internal data contracts.
- Core: config, exceptions, middleware, logging, security.

## API Flow

`POST /v1/query` lifecycle:

1. Validate and sanitize input.
2. Run vagueness detection (Ollama first, with service-level fallback).
3. If vague: return clarification prompt.
4. If clear: run category/product reasoning through provider fallback chain.
5. Enrich categories with SerpAPI listings when available.
6. Return structured recommendations response.

## AI Provider Stack

Vagueness detection:

- Ollama (primary)
- OpenAI mini model (internal fallback in vagueness service)

Category and product reasoning fallback order:

1. Gemini
2. GROQ
3. OpenAI
4. Ollama (final fallback)

Fallback triggers on:

- API request errors
- timeout
- unavailable/misconfigured provider
- invalid response schema

## Main Endpoint

`POST /v1/query`

Request example:

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_message": "I need lightweight trekking gear under 150 dollars",
  "conversation_history": [
    { "role": "user", "content": "I need trekking gear" }
  ]
}
```

Response example (clarification):

```json
{
  "status": "clarification_needed",
  "message": "What budget range should I target?",
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

Response example (recommendations):

```json
{
  "status": "recommendations",
  "categories": [
    {
      "category": "lightweight trekking backpack",
      "products": [
        {
          "title": "Trekking Backpack 35L",
          "price": "$89",
          "url": "https://example.com/product/123",
          "image_url": "https://example.com/image.jpg",
          "source": "Retailer",
          "rating": 4.6,
          "explanation": "Good weight-capacity tradeoff for short treks."
        }
      ]
    }
  ],
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

## Setup

1. Install dependencies.
2. Configure `.env` (optionally start from `Environment/.env.example`).
3. Start the API.

```bash
pip install -r Requirements/requirements.txt
uvicorn app.main:app --reload
```

Install dev tooling:

```bash
pip install -r Requirements/requirements-dev.txt
```

## Environment Variables

Required or commonly used:

- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- `GROQ_API_KEY`
- `OLLAMA_URL`
- `OLLAMA_MODEL`
- `SERPAPI_KEY`
- `REDIS_URL`
- `CORS_ORIGINS`
- `RATE_LIMIT_PER_MINUTE`
- `SESSION_TTL_MINUTES`

Model overrides:

- `OPENAI_MODEL` (default: `gpt-4o`)
- `GEMINI_MODEL` (default: `gemini-1.5-flash`)
- `GROQ_MODEL` (default: `llama-3.1-70b-versatile`)

## Running the Server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Health check:

```bash
curl http://localhost:8000/v1/health
```

## Project Structure

```text
RecommendMe-API/
|-- app/
|   |-- api/
|   |   |-- v1/
|   |   |   |-- health.py
|   |   |   `-- query.py
|   |   |-- deps.py
|   |   `-- README.md
|   |-- core/
|   |   |-- config.py
|   |   |-- exceptions.py
|   |   |-- logger.py
|   |   |-- middleware.py
|   |   `-- security.py
|   |-- models/
|   |   |-- internal.py
|   |   |-- requests.py
|   |   `-- responses.py
|   |-- prompts/
|   |   |-- category_reasoning.py
|   |   |-- intent_extraction.py
|   |   |-- product_ranking.py
|   |   `-- vagueness_check.py
|   |-- providers/
|   |   |-- base.py
|   |   |-- gemini_provider.py
|   |   |-- groq_provider.py
|   |   |-- openai_provider.py
|   |   `-- ollama_provider.py
|   |-- services/
|   |   |-- cache.py
|   |   |-- products.py
|   |   |-- ranking.py
|   |   |-- recommender.py
|   |   `-- vagueness.py
|   |-- utils/
|   |   |-- formatters.py
|   |   |-- session.py
|   |   `-- validators.py
|   `-- main.py
|-- docs/
|   |-- api_architecture.md
|   |-- ai_model_pipeline.md
|   `-- project_structure.md
|-- Dockerfile
|-- docker-compose.yml
|-- main.py
|-- requirements.txt
`-- README.md
```

## Additional Documentation

- `app/api/README.md`
- `docs/api_architecture.md`
- `docs/ai_model_pipeline.md`
- `docs/project_structure.md`

## Environment file (.env) — format

This project reads local environment variables from a `.env` file for development. This file often contains sensitive API keys and must NOT be committed to the repository. Add `.env` to your global or repository `.gitignore`.

Example `.env` template (replace placeholders with real values locally):

```
OPENAI_API_KEY=your_openai_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
GROQ_API_KEY=your_groq_api_key_here
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=ollama-model-name
SERPAPI_KEY=your_serpapi_key_here
REDIS_URL=redis://localhost:6379/0
CORS_ORIGINS=http://localhost:3000
RATE_LIMIT_PER_MINUTE=60
SESSION_TTL_MINUTES=60
```

- **Do not** paste real keys into issues, PRs, or shared repos. Rotate any keys that were accidentally committed.
- Keep `Environment/.env.example` (without secrets) in the repo for onboarding.
