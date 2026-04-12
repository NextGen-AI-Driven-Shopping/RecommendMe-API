# Logical Flow

## Startup Flow

1. Load settings and initialize logger.
2. Run startup cache cleanup.
3. Build FastAPI app with lifespan hooks.
4. Register CORS, middleware, and exception handlers.
5. Mount v1 router.
6. Expose root and liveness endpoints.

## Query Flow (`POST /v1/query`)

1. Input sanitization and validation.
2. Session snapshot initialization/update.
3. Intent/domain detection.
4. Clarification branch selection:
- Clarification payload present -> sufficiency planning.
- Clarification payload absent -> vagueness classification.
5. Clarification response path:
- return one next question and persist state.
6. Recommendation response path:
- generate category plan.
- fetch products per product type.
- persist progressive session snapshots.
- return recommendation payload.

## Sufficiency Check Flow (`POST /v1/query/sufficiency_check`)

1. Validate query.
2. Run clarification planner next-step logic.
3. Return score and next questions.

## Session Flow

1. Session retrieved by id from in-memory store.
2. Expired sessions are evicted on access.
3. Snapshot updates occur during query/chat processing.
4. Session hydration endpoints return normalized state payload.

## Auth Flow

## Signup

1. Validate payload and uniqueness.
2. Hash password + store user in CSV.
3. Upsert default profile in JSON store.
4. Issue auth token.

## Login

1. Resolve dev/prod credential branch.
2. Validate credentials against CSV where required.
3. Upsert profile and optional session auth state.
4. Issue auth token.

## Password Reset

1. Forgot-password creates reset token and expiry metadata in profile store.
2. Reset-password resolves token, updates CSV password hash, clears reset metadata.

## Profile Flow

1. Load profile (or default) for authenticated user.
2. Apply update merges on create/update endpoints.
3. Handle avatar list and upload operations.

## Chat Mode Flow (`POST /v1/chat/mode`)

1. Validate session exists.
2. Ensure recommendation context is available.
3. Build context package from session and optional profile data.
4. Generate answer (provider path, then heuristic fallback).
5. Append conversation messages and persist session update.

## Health Flow (`GET /v1/health`)

1. Build key configuration status indicators.
2. Probe Ollama endpoint.
3. Probe Redis endpoint if configured.
4. Return structured health status model.

## Cross-Cutting Flow Controls

- Middleware injects correlation id and request timing logs.
- Global exception handlers standardize error responses.
- CORS policy is applied globally from settings.
