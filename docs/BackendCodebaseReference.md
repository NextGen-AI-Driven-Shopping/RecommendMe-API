# Superseded Document

This file is retained for historical context. For current implementation-accurate backend documentation, use:
- backend_overview.md
- architecture.md
- api_reference.md
- data_flow.md
- ai_integration.md

---

# Backend Codebase Reference

Last verified: 2026-04-13

## Reference Scope

This file is the consolidated technical reference for backend implementation facts that are directly traceable to source code and configuration.

## Verified Runtime Checks

Executed in this workspace:
- `python -m compileall app` -> success
- `python -m pytest -q tests` -> `50 passed`
- `python -c "... import app.main ..."` -> success
- `python -c "... import app.services.ranking ..."` -> success
- `python -c "... import app.services.suggestions ..."` -> success

## Backend Scope Summary

- Framework: FastAPI
- API namespace: `/v1`
- Auth storage: CSV
- Profile storage: JSON
- Session storage: in-memory
- AI provider adapters: Groq, OpenAI, Gemini, Ollama
- Product retrieval: SerpAPI primary, direct Google fallback

## Contract Summary

Request models:
- `QueryRequest`, `SufficiencyCheckRequest`, `ChatModeRequest`
- `SignupRequest`, `LoginRequest`, `ForgotPasswordRequest`, `ResetPasswordRequest`
- `ProfileUpdateRequest`

Response models:
- `QueryResponse`, `SufficiencyCheckResponse`, `HealthResponse`
- `AuthSignupResponse`, `AuthLoginResponse`, `PasswordResetResponse`
- `ProfileResponse`, `AvatarOptionsResponse`
- `ChatSessionState`, `ChatModeResponse`

## Key Data Stores

- `app/data/users.csv`
- `app/data/profiles.json`
- `app/utils/session.py` in-memory map with TTL eviction on access

## Known Implementation Constraints

- No active rate-limit middleware despite rate-limit settings field.
- Session TTL settings field does not currently drive session module constant.
- Session/cache state is process-local.
- Query request deduplication cache is process-local and memory-backed.
- Dev login bypass requires explicit opt-in via `ALLOW_DEV_LOGIN_BYPASS=true` and `APP_ENV=development`.

## Determinability

Not determinable from the current codebase:
- production traffic and SLA targets.
- external scheduled cleanup jobs.
- intended future status of disabled workflow jobs.

