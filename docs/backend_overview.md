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
- `AIServiceException` (503) for all AI provider chain failures.
- `AuthenticationException` (401) for invalid/missing tokens.
- Global exception handlers in `app/core/exceptions.py` map to JSON responses with detail messages.
- Unhandled exceptions return 500 with generic message (no stack trace to client).

## AI Provider Chain Details

The system implements a robust fallback chain across multiple AI providers:

### Provider Priority Order
1. **Groq** - fastest, primary
   - Models: `mixtral-8x7b-32768`, `gemma2-9b-it`
   - Max retries: 2
   - Best for: fast clarification and recommendations

2. **OpenAI** - high quality, fallback
   - Models: `gpt-4`, `gpt-3.5-turbo`
   - Max retries: 1
   - Best for: complex reasoning

3. **Gemini** - Google's model, secondary fallback
   - Models: `gemini-1.5-pro`, `gemini-1.5-flash`
   - Max retries: 1
   - Best for: multimodal tasks

4. **Ollama** - local/self-hosted, final fallback
   - Models: configurable in `provider_models.yml`
   - Max retries: 2
   - Best for: offline operation

### Fallback Algorithm
```
For each step (vagueness, clarification, recommendation):
  For each provider in [Groq, OpenAI, Gemini, Ollama]:
    For each attempt in [1..MAX_RETRIES]:
      Try to call provider with model list
      If success: return result
      If timeout/auth error: continue to next provider
      If rate limit: log and continue
  If all providers exhausted:
    Return None (triggers error response)
```

## Request Deduplication

Prevents duplicate recommendations if the same request is sent multiple times:

- Cache key: `request_id` (provided by client or generated)
- TTL: 30 seconds
- Storage: in-process dict (`request.app.state.request_cache`)
- Behavior:
  - On cache hit: return cached response immediately
  - On cache miss: process request normally, cache result
  - Stale entries pruned on each request

## Session Management

Session state is maintained for conversation continuity:

- **TTL**: 1800 seconds (30 minutes) of inactivity
- **Storage**: in-process dict with threading lock
- **Contents**: message history, clarification answers, latest response, metadata
- **Locking**: `threading.RLock` for concurrent access safety
- **Limitation**: NOT shared across multiple server instances (single process only)

For production multi-process deployments, implement Redis-backed session store.

## Logging Architecture

All events logged using structured JSON format:

- **Output**: 
  - stdout (development)
  - rotating file: `app/core/logs/app.log` (production)
- **Fields**: timestamp, level, correlation_id, module, message, structured fields
- **Correlation ID**: propagated through request lifecycle via X-Correlation-ID header
- **Request timing**: duration_ms logged for performance monitoring

## CSV and JSON Data Persistence

### Users (app/data/users.csv)
Fields:
- `user_id`: UUID string
- `username`: unique login identifier
- `first_name`: user's first name
- `last_name`: user's last name  
- `email`: contact email
- `phone`: contact phone
- `password_hash`: PBKDF2 hash
- `password_salt`: salt used in hashing
- `created_at`: ISO-8601 timestamp

Password hashing uses PBKDF2 with SHA256, 100,000 iterations.

### Profiles (app/data/profiles.json)
Structure: `{user_id: {...profile_data}}`

Profile fields:
- `user_id`: reference to user
- `username`: denormalized from user
- `email`: contact email
- `gender`: user's gender preference
- `age`: optional age in years
- `interests`: list of interest tags
- `about`: free-text bio
- `avatar_url`: CDN path to avatar image
- `avatar_file_path`: local file path (if custom upload)
- `created_at`: profile creation timestamp
- `updated_at`: last modification timestamp
- `reset_token`: optional password reset token (temporary)

## CORS Configuration

CORS is enforced via two mechanisms:

1. **Exact origins list**: `Settings.CORS_ORIGINS`
   - Example: `["https://example.com"]`

2. **Regex pattern**: `Settings.CORS_ORIGIN_REGEX`
   - Example: `r"^https?://(localhost|127\.0\.0\.1):\d+$"` for local dev
   - Allows any port on localhost/127.0.0.1

Credentials are allowed if origin match is successful.

## SERP API Integration

Product retrieval from SerpAPI Google Shopping:

- **Endpoint**: `https://serpapi.com/search`
- **Engine**: `google_shopping`
- **Parameters**:
  - `q`: normalized product type name + optional context
  - `hl`: `en` (English)
  - `gl`: `in` (India for INR pricing)
  - `num`: max 10 results
- **Timeout**: 8 seconds per request
- **Quota handling**: 
  - HTTP 429 → permanently disables SERP for process lifetime
  - Fallback: return empty list (frontend shows description-only)
- **Price normalization**: converts to INR with ₹ symbol
- **Fallback on failure**: shows product types without items

## Performance Constraints

- **Query length**: min 3, max 500 characters
- **Conversation history**: max 30 messages before truncation
- **Product items per type**: max 10 items
- **Product types per session**: max 10 types
- **Follow-up questions**: always exactly 5 total (3 round1 + 2 round2)
- **API request timeout**: SDK default 30 seconds per HTTP call
- **SERP request timeout**: 8 seconds
- **Concurrent SERP fetches**: limited to 4 simultaneous requests per recommendation

## Security Best Practices

1. **Token validation**: every protected route checks token signature and expiry
2. **Password hashing**: PBKDF2 with 100k iterations, never stored plain
3. **Input sanitization**: null-byte stripping, length enforcement, pattern detection
4. **CORS enforcement**: origin validation before response
5. **No hardcoded secrets**: all keys from environment variables
6. **Bearer token auth**: standard `Authorization: Bearer <token>` header
7. **SQLi/XSS prevention**: parameterized CSV/JSON reads, JSON encoding of responses
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
