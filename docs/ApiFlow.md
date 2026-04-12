# API Flow

## API Surface

Base API namespace: `/v1`

Public root/liveness routes:
- `GET /`
- `GET /health`

## Endpoint Inventory

| Method | Path | Auth | Request Model | Response Model |
|---|---|---|---|---|
| GET | `/` | Public | None | Inline JSON |
| GET | `/health` | Public | None | Inline JSON |
| GET | `/v1/health` | Public | None | `HealthResponse` |
| POST | `/v1/query` | Public | `QueryRequest` | `QueryResponse` |
| POST | `/v1/query/sufficiency_check` | Public | `SufficiencyCheckRequest` | `SufficiencyCheckResponse` |
| GET | `/v1/sessions/{session_id}` | Public | Path param | `ChatSessionState` |
| GET | `/v1/sessions/{session_id}/exists` | Public | Path param | Inline JSON |
| POST | `/v1/chat/mode` | Public | `ChatModeRequest` | `ChatModeResponse` |
| POST | `/v1/auth/signup` | Public | `SignupRequest` | `AuthSignupResponse` |
| POST | `/v1/auth/login` | Public | `LoginRequest` | `AuthLoginResponse` |
| POST | `/v1/auth/forgot-password` | Public | `ForgotPasswordRequest` | `PasswordResetResponse` |
| POST | `/v1/auth/reset-password` | Public | `ResetPasswordRequest` | `PasswordResetResponse` |
| GET | `/v1/auth/me` | Bearer | None | Inline JSON |
| GET | `/v1/profile` | Bearer | None | `ProfileResponse` |
| POST | `/v1/profile` | Bearer | `ProfileUpdateRequest` | `ProfileResponse` |
| PUT | `/v1/profile/update` | Bearer | `ProfileUpdateRequest` | `ProfileResponse` |
| GET | `/v1/profile/avatars` | Public | None | `AvatarOptionsResponse` |
| POST | `/v1/profile/avatar/upload` | Bearer | Multipart file | `ProfileResponse` |

## Primary Query Flow (`POST /v1/query`)

1. Validate input (`sanitize_and_validate_query`).
2. Create or update session snapshot.
3. Detect domain and intent (`classify_intent`).
4. Branch:
- If clarification payload exists: run sufficiency planner.
- Else: run vagueness classification.
5. If insufficient/vague: return clarification response with one next question.
6. If clear/sufficient: generate category plan (`generate_category_plan`).
7. Fetch products per product type (`fetch_products`) with fallback behavior.
8. Persist progressive snapshots while fetching.
9. Return recommendation response with `data_source` and `degraded` flags.

## Sufficiency Flow (`POST /v1/query/sufficiency_check`)

1. Validate input.
2. Run `ClarificationPlanner.plan_next_step`.
3. Return sufficiency score and next questions.

## Session Retrieval Flow (`GET /v1/sessions/{session_id}`)

1. Load session from in-memory store.
2. If absent/expired: return a synthetic `new` session payload.
3. If present: normalize and return full state (`messages`, `latest_response`, question metadata).

## Chat Mode Flow (`POST /v1/chat/mode`)

1. Load session by `session_id`.
2. Ensure recommendation context exists (`product_types` or legacy `categories`).
3. Build context package (query, clarifications, profile, category, items).
4. Try provider chain for follow-up answer.
5. If providers fail, return heuristic answer.
6. Append user and assistant messages to session.

## Auth Flow

### Signup

1. Validate payload.
2. Create user in CSV auth store.
3. Upsert profile in JSON store.
4. Issue auth token.
5. Return user + token payload.

### Login

1. Resolve dev-mode bypass rules (`APP_ENV != production`).
2. Validate credentials against CSV store when required.
3. Upsert profile.
4. Optionally update linked session status.
5. Return user + token payload.

## Profile Flow

- `GET /v1/profile`: load existing or create default profile.
- `POST/PUT /v1/profile...`: merge updates and persist.
- `POST /v1/profile/avatar/upload`: validate MIME/size, write file, update stored avatar path.

## Health Flow

`GET /v1/health` returns a consolidated health payload:
- Configured/not configured status for API-key-based services.
- Reachability probes for Ollama and Redis.
