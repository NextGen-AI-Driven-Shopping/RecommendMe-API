# Backend Overview

## Scope
This document describes the implemented backend in `RecommendMe-API/app` as of 2026-04-13.
It is implementation-derived and intentionally excludes behavior that is not present in code.

## Runtime Summary
- Framework: FastAPI (`app/main.py`)
- Entry point: `main.py` (`uvicorn app.main:app`)
- API prefix: `/v1` (router aggregation in `app/routes/v1/router.py`)
- Data stores:
  - CSV file for auth users (`app/data/users.csv`)
  - JSON file for profiles (`app/data/profiles.json`)
  - In-process memory for chat sessions (`app/utils/session.py`)
  - In-process request de-duplication cache (`app.state.request_cache`)
- External dependencies:
  - AI providers: Groq, OpenAI, Gemini, Ollama (fallback chain)
  - Product retrieval: SerpAPI Google Shopping
  - Optional health probes: Ollama endpoint and Redis ping

## High-Level Architecture
- API layer (`app/routes/v1`): HTTP contract and orchestration.
- Service layer (`app/services`): AI classification/question/recommendation flow, product retrieval, auth and profile persistence.
- Domain models:
  - Request/response API schemas: `app/models/requests.py`, `app/models/responses.py`
  - Internal pipeline models: `app/models/internal.py`
- Platform layer (`app/core`): logging, middleware, exception mapping, auth dependency, CORS.
- Utilities (`app/utils`): validation, response formatting, prompt helpers, session store.
- Prompt templates (`app/prompts`): strict JSON-output instructions for LLM steps.

## Implemented Backend Modules

### `app/config`
- `settings.py`: environment-driven configuration using `pydantic-settings`, including model list parsing and provider model defaults from `provider_models.yml`.
- `provider_models.yml`: configured model preference order per provider.

### `app/core`
- `auth.py`: bearer-token dependency (`get_current_user`) with token verification and CSV user lookup.
- `exceptions.py`: custom exception classes and global handlers.
- `logger.py`: JSON structured logging to stdout and rotating file (`app/core/logs/app.log`).
- `middleware.py`: correlation-id + request timing/logging middleware.
- `security.py`: CORS middleware setup.
- `cache_cleaner/cleaner.py`: startup cleanup of cache artifacts.

### `app/routes/v1`
- `router.py`: mounts route modules under `/v1`.
- `health.py`: `/v1/health` status endpoint with provider probes.
- `query.py`: main recommendation pipeline endpoint.
- `auth.py`: signup/login/password reset/me.
- `profile.py`: profile read/update/avatar operations.
- `sessions.py`: read session snapshot and existence check.
- `chat_mode.py`: post-recommendation follow-up chat endpoint.

### `app/services` (active path)
- `vagueness.py`: query classification and shared provider fallback chain.
- `clarification_runtime.py`: pre-clarification + round 1/2 question generation.
- `recommender.py`: recommendation-plan generation (category + product types).
- `products.py`: SerpAPI item fetch and normalization.
- `chat_mode.py`: contextual answer generation after recommendations.
- `auth_csv.py`: CSV-backed auth service with PBKDF2 hashing.
- `auth_token.py`: HMAC-signed bearer token creation/verification.
- `profile_store.py`: JSON-backed profile store.

### `app/services` (present but not on primary route path)
- `clarification.py`, `cache.py`, `ranking.py`, `suggestions.py` are present but not used by current route handlers.
- `app/providers/*_provider.py` exists as adapter code, but the active AI calls are performed via `app/services/vagueness.py` provider-chain functions.

## Request Lifecycle
1. Request enters FastAPI app.
2. CORS middleware applies policy.
3. Request logging middleware assigns/propagates `X-Correlation-ID`, times execution, logs structured event.
4. Route-level validation uses Pydantic models.
5. Business flow executes in route/service layer.
6. Custom exceptions map to JSON (`{"detail": ...}`), unhandled exceptions return 500 with generic detail.

## Data Handling
- No relational/NoSQL database integration in current implementation.
- User accounts:
  - Stored in CSV with fields: `user_id, username, first_name, last_name, email, phone, password_hash, password_salt, created_at`.
- Profiles:
  - Stored in JSON keyed by `user_id`.
- Sessions:
  - In-memory dict with TTL (default 30 minutes).
  - Not shared across multi-process instances.

## Authentication
- Token format: compact custom token (`base64(payload).base64(signature)`), HMAC-SHA256 signature.
- Token payload: `sub` (user_id), `sid` (session_id), `iat`, `exp`.
- Protected endpoints use `Depends(get_current_user)`.
- Protected routes:
  - `GET /v1/auth/me`
  - `GET /v1/profile`
  - `POST /v1/profile`
  - `PUT /v1/profile/update`
  - `POST /v1/profile/avatar/upload`
- Public routes include recommendations, health, sessions, chat mode, and `GET /v1/profile/avatars`.

## Error Handling Strategy
- Expected business errors use `HTTPException` with explicit status codes.
- `ValidationException` (422) for query input validation failure.
- `AIServiceException` (503) for AI unavailability/failure in recommendation path.
- Global `HTTPException` handler returns `{ "detail": <message> }`.
- Global unhandled exception handler logs traceback and returns 500 generic response.

## Async and Concurrency
- Async calls use `httpx.AsyncClient`.
- Product fetch fanout (`/v1/query`) uses `asyncio.gather` with `asyncio.Semaphore(4)` to bound concurrency.
- Vagueness classification provider attempts use retry wrapper (`2` attempts/provider).
- SerpAPI fetch retries once when first attempt returns empty/error.
- Thread-safety for mutable stores:
  - Session store uses `threading.RLock`.
  - CSV/profile file operations use locks.

## Performance Characteristics
- Request de-duplication (`request_id`) with TTL 30 seconds avoids repeated work for duplicate submissions.
- Model/provider fallback attempts increase robustness but can add latency in failure scenarios.
- Product fetch parallelization reduces wall-clock time for multi-type recommendations.
- In-memory stores are fast but non-distributed and reset on process restart.

## Notable Documentation Drift Fixed
- `POST /v1/query/sufficiency_check` is not implemented in current routes.
- Root health endpoint is `/health` (outside `/v1`) and lightweight; `/v1/health` includes dependency probe statuses.
- `tests/` directory is currently empty.
