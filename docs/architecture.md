# Backend Architecture

## System Design

```text
Client
  -> FastAPI app (app/main.py)
      -> Middleware
          - CORS
          - Request logging + correlation id
      -> v1 router (/v1)
          -> Route handlers
              -> Services (AI/auth/profile/products)
                  -> External providers (Groq/OpenAI/Gemini/Ollama, SerpAPI)
                  -> File stores (users.csv, profiles.json)
                  -> In-memory stores (sessions, request cache)
```

## Component Interaction
- `app/main.py` composes platform concerns and mounts routes.
- Route handlers orchestrate flow and shape response models.
- Services hold business logic and external I/O.
- Internal models represent pipeline entities (`ProductType`, `RecommendationResult`, `QuestionWithOptions`).
- Response formatter utilities map internal models to API contracts.

## Detailed Layering

| Layer | Key Files | Responsibility |
|---|---|---|
| App bootstrap | `app/main.py` | app creation, lifespan hooks, route mount |
| Platform/core | `app/core/*` | auth dependency, exception mapping, logging, middleware, CORS |
| Route/API | `app/routes/v1/*` | endpoint contracts and orchestration |
| Services | `app/services/*` | AI calls, fallback logic, product retrieval, auth/profile persistence |
| Models | `app/models/*` | typed schemas for requests/responses and internal pipeline objects |
| Utilities | `app/utils/*` | validation, prompt/message helpers, session store, response formatting |
| Prompt contracts | `app/prompts/*` | strict prompts for vagueness/clarification/recommendation generation |

## Runtime State and Storage

### 1. In-Memory Runtime State
- `request.app.state.request_cache`
  - Purpose: request de-duplication by `request_id`.
  - TTL: 30 seconds.
  - Structure: `{request_id: {timestamp, response}}`.
- `app/utils/session.py` store
  - Purpose: chat session continuity.
  - TTL: 1800 seconds.
  - Locking: `threading.RLock`.

### 2. Persistent Files
- `app/data/users.csv`
  - Auth identity records and hashed passwords.
- `app/data/profiles.json`
  - User profile + optional password reset token metadata.
- `app/data/uploads/avatars`
  - Uploaded avatar files from `POST /v1/profile/avatar/upload`.

## Route Composition
- Global routes:
  - `GET /`
  - `GET /health`
- Versioned routes:
  - mounted through `app/routes/v1/router.py` with prefix `/v1`

## Security Architecture

### Token Auth
- Signing: HMAC-SHA256 with `AUTH_TOKEN_SECRET`.
- Payload includes subject and optional session id.
- Validation performed in `app/core/auth.py`.

### Input Safety
- `sanitize_and_validate_query` enforces:
  - min/max length
  - null-byte cleanup
  - blocked injection-like patterns

### CORS
- Exact origins from `Settings.CORS_ORIGINS` plus regex from `Settings.CORS_ORIGIN_REGEX`.

## AI Orchestration Architecture

### Shared Provider Chain
`app/services/vagueness.py::_try_provider_chain`
- Provider order: Groq -> OpenAI -> Gemini -> Ollama.
- Each provider tries a short candidate model list from settings defaults.
- Returns raw text output or `None`.

### Functional AI Steps
- Vagueness classification: `classify_vagueness`.
- Clarification generation:
  - pre-clarification (1 question)
  - round 1 (3 questions)
  - round 2 (2 questions)
- Recommendation plan generation:
  - one category
  - up to ten product types with descriptions
- Chat mode follow-up answer generation using full session context.

## Async Execution Model
- Endpoint handlers are async.
- Remote calls use async HTTP clients.
- Product fetch is fan-out with bounded concurrency (`Semaphore(4)`).
- Session/profile/csv stores use locks for local process thread safety.

## Reliability and Failure Behavior
- Provider/model fallback for AI steps.
- Retry loops:
  - vagueness provider attempts: 2 per provider.
  - SerpAPI fetch: one retry.
- Graceful degradation:
  - recommendation can return without product cards when all SERP calls fail.
  - chat mode returns a safe message when all AI providers fail.

## Important Boundaries
- No database migrations or ORM layer in current backend.
- No queue/broker worker architecture.
- Session and request-cache state are process-local and not shared across replicas.
