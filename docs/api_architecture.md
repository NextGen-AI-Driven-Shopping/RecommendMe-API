# API Architecture

## Purpose

RecommendMe API exposes a stable HTTP interface for shopping recommendation workflows while isolating AI-provider volatility behind a service abstraction.

## Consumers

- Frontend applications integrating guided product discovery.
- Backend clients that require deterministic response schemas.
- Internal AI workflow consumers needing fallback-safe orchestration.

## Architectural Layers

- `app/api/`: route handlers and API contracts.
- `app/services/`: domain orchestration logic.
- `app/providers/`: provider adapters with uniform output validation.
- `app/prompts/`: reusable prompt definitions.
- `app/models/`: Pydantic contracts for request/response/internal data.
- `app/core/`: configuration, middleware, logging, exception handling.

## Endpoint Design

Main endpoint:

- `POST /v1/query`

Supporting endpoint:

- `GET /v1/health`

Design characteristics:

- Stateless request processing with optional session continuity.
- Pydantic-validated payloads.
- Centralized exception-to-HTTP mapping.
- Structured JSON logs.

## Query Lifecycle

User Query
-> sanitize and validate
-> vagueness detection (Ollama)
-> clarification response if vague
-> provider orchestration for category reasoning
-> SerpAPI enrichment (when configured)
-> structured response assembly

## Reliability Strategy

- Provider abstraction hides API-specific details.
- Hard fallback order for category reasoning:
  1. Gemini
  2. GROQ
  3. OpenAI
  4. Ollama
- Fallback on timeout, HTTP errors, invalid payloads, or missing credentials.
