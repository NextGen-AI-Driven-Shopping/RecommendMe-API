# API Architecture

## Purpose

RecommendMe API exposes stable contracts for conversational shopping recommendations.

## Layered Design

- `app/routes/v1` - HTTP route handlers and response contracts
- `app/services` - orchestration and business logic
- `app/providers` - LLM adapters with normalized payload validation
- `app/models` - request/response schemas
- `app/prompts` - prompt templates
- `app/core` - middleware, exceptions, security, logging

## Core Endpoints

- `POST /v1/query`
- `POST /v1/query/sufficiency_check`
- `POST /v1/auth/signup`
- `POST /v1/auth/login`
- `GET /v1/health`

## Query Lifecycle

1. Validate and sanitize user input.
2. Vagueness classification.
3. If vague: return guided follow-ups.
4. If clear: run category reasoning with tiered LLM fallback.
5. Fetch and rank category products.
6. Return normalized recommendation response.

## Reliability Strategy

Reasoning fallback tiers:

1. Groq (up to 4 models)
2. OpenAI (up to 4 models)
3. Gemini (up to 4 models)

If all fail, return:

`All AI services are currently busy. Please try again in a moment.`

## Integration Contracts

- Backend response model uses `status` (`clarification_needed` or `recommendations`)
- Frontend normalizes this model to UI-specific type handling
- Auth endpoints return user profile + token (MVP session storage)
