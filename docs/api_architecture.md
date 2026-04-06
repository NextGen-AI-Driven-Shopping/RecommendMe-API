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
- `app/utils/session.py` - in-memory session snapshot persistence

## Core Endpoints

- `POST /v1/query`
- `POST /v1/query/sufficiency_check`
- `GET /v1/sessions/{session_id}`
- `GET /v1/sessions/{session_id}/exists`
- `POST /v1/auth/signup`
- `POST /v1/auth/login`
- `POST /v1/auth/forgot-password`
- `POST /v1/auth/reset-password`
- `GET /v1/auth/me`
- `GET /v1/profile`
- `POST /v1/profile`
- `PUT /v1/profile/update`
- `GET /v1/profile/avatars`
- `POST /v1/profile/avatar/upload`
- `GET /v1/health`

## Query Lifecycle

1. Validate and sanitize user input.
2. Vagueness classification.
3. If vague: return guided follow-ups.
4. If clear: run category reasoning with tiered LLM fallback.
5. Persist progressive recommendation snapshots as category/product data arrives.
6. Fetch and rank category products (SerpAPI primary, direct Google fallback on failure).
7. Return normalized recommendation response.

## Reliability Strategy

Reasoning fallback tiers:

1. Groq (up to 4 models)
2. OpenAI (up to 4 models)
3. Gemini (up to 4 models)
4. Ollama local fallback

If all fail, return:

`All AI services are currently unavailable. Please try again later.`

## Integration Contracts

- Backend response model uses `status` (`clarification_needed` or `recommendations`)
- Frontend normalizes this model to UI-specific type handling
- Sessions endpoint returns hydratable chat snapshots for progressive UI updates
- Auth endpoints return token, user profile, and optional session linkage
