# Superseded Document

This file is retained for historical context. For current implementation-accurate backend documentation, use:
- backend_overview.md
- architecture.md
- api_reference.md
- data_flow.md
- ai_integration.md

---

# Error Handling Strategy

## Design Intent

The backend uses layered error handling:
- Input-level rejection at validation boundaries.
- Domain/service exceptions for recoverable and provider-specific failures.
- Route-level translation to HTTP response semantics.
- Global fallback for unexpected exceptions.

## Exception Types

### Core HTTP Exceptions

Defined in `app/core/exceptions.py`:
- `BaseAPIException`
- `AIServiceException` (503)
- `RateLimitException` (429)
- `ValidationException` (422)

### Service-Level Exceptions

Examples:
- `VaguenessServiceError`
- `RecommendationServiceError`
- Auth errors (`AuthValidationError`, `AuthConflictError`, `AuthNotFoundError`, `AuthCredentialsError`)
- Provider errors (`ProviderError`, `ProviderUnavailableError`, `ProviderResponseError`)

## Route-Level Handling Patterns

### Query Routes

- Invalid input -> `ValidationException`.
- Provider orchestration failure -> translated to `AIServiceException` with busy message.
- Product/category fetch failures are skipped when possible; request fails only if no category can produce live or fallback items.

### Auth Routes

- Validation/conflict/credentials issues are mapped to precise HTTP status codes (400/401/404/409).

### Profile Routes

- Missing profile after update path -> HTTP 404.
- Avatar validation failures -> HTTP 400.

## Provider Fallback Error Strategy

### Vagueness Classification

Provider sequence:
- Groq -> OpenAI -> Gemini -> Ollama

Behavior:
- Single provider failure does not fail request.
- Provider attempts are retried and logged.
- If all providers fail, route returns retry/busy semantics.

### Category Reasoning

Provider sequence:
- Groq -> OpenAI -> Gemini -> Ollama

Behavior:
- Provider-level errors are collected.
- Final failure raises `RecommendationServiceError`.

### Product Fetching

- SerpAPI 429 marks process-level SerpAPI unavailable.
- SerpAPI auth/HTTP/network failures fall back to direct Google fetch.
- Full fetch failure returns `None`, and caller decides whether to skip category or emit search-link fallback cards.

## Global Exception Handling

Registered in `register_exception_handlers(app)`:
- HTTP exceptions: serialized to `{"detail": ...}`.
- Unhandled exceptions: logged with traceback, returned as generic 500.

## Logging And Correlation

### Request Middleware

- Generates/propagates `X-Correlation-ID`.
- Logs request method, URL, status, duration, client metadata.

### Structured Logging

- JSON logs to stdout and rotating file `app/core/logs/app.log`.
- Provider and request metrics are logged with context.

## Current Gaps (Code-Evident)

- Rate-limit exception class exists, but active rate-limit middleware is not wired in current runtime path.
- Session cleanup is opportunistic on access (no background cleanup worker).
- Request deduplication cache is in-memory and process-local, so dedupe does not span multiple API instances.

