# Superseded Document

This file is retained for historical context. For current implementation-accurate backend documentation, use:
- backend_overview.md
- architecture.md
- api_reference.md
- data_flow.md
- ai_integration.md

---

# Component Responsibilities

## Scope

This document details major backend components/files and explains:
- What the component does.
- Why it exists.
- How it works.
- How it connects to other parts of the system.
- Key functions/classes.
- Inputs and outputs.

## Runtime Entry And App Composition

## `main.py` (root)

- Purpose: start the development server quickly.
- Justification: developer convenience entry point.
- Internal logic: runs `uvicorn app.main:app`.
- Connections: delegates to `app/main.py` application object.
- Key symbols: none (script-style launcher).
- Inputs/Outputs:
  - Input: process start.
  - Output: running HTTP server.

## `app/main.py`

- Purpose: FastAPI application factory and startup configuration.
- Justification: single assembly point for middleware, handlers, and routers.
- Internal logic:
  - pre-start cache cleanup.
  - lifespan startup/shutdown hooks.
  - CORS, middleware, exception handler registration.
  - mount v1 router.
  - define `/` and `/health` routes.
- Connections:
  - `app/core/*` for cross-cutting concerns.
  - `app/routes/v1/router.py` for endpoints.
- Key symbols:
  - `lifespan`
  - `app`
  - `root`
  - `liveness`
- Inputs/Outputs:
  - Input: framework startup lifecycle.
  - Output: configured FastAPI app.

## API Route Layer

## `app/routes/v1/query.py`

- Purpose: main recommendation and sufficiency endpoints.
- Justification: central HTTP gateway for query orchestration.
- Internal logic:
  - validate request.
  - initialize/update session.
  - detect domain/intent.
  - run clarification/vagueness logic.
  - generate category plan and fetch products.
  - return clarification or recommendation response.
- Connections:
  - services: `clarification`, `intent_engine`, `vagueness`, `recommender`, `products`.
  - utils: `validators`, `formatters`, `session`.
- Key symbols:
  - `handle_query`
  - `sufficiency_check`
  - helper functions for message/session/product fetch orchestration.
- Inputs/Outputs:
  - Input: `QueryRequest`, `SufficiencyCheckRequest`.
  - Output: `QueryResponse`, `SufficiencyCheckResponse`.

## `app/routes/v1/auth.py`

- Purpose: signup/login/password-reset/me endpoints.
- Justification: isolate authentication HTTP contract from storage/service details.
- Internal logic:
  - call CSV auth service for user CRUD/auth checks.
  - issue and verify auth tokens.
  - upsert profile defaults.
- Connections:
  - `app/services/auth_csv.py`
  - `app/services/auth_token.py`
  - `app/services/profile_store.py`
  - `app/core/auth.py`
- Key symbols:
  - `signup`, `login`, `forgot_password`, `reset_password`, `me`
- Inputs/Outputs:
  - Input: auth request models.
  - Output: auth response models and user/session payload.

## `app/routes/v1/profile.py`

- Purpose: profile CRUD and avatar operations.
- Justification: profile lifecycle endpoint boundary.
- Internal logic:
  - load/upsert profile.
  - update selected profile fields.
  - validate avatar file constraints and persist upload.
- Connections:
  - `app/services/profile_store.py`
  - `app/core/auth.py`
- Key symbols:
  - `get_profile`, `create_profile`, `update_profile`, `list_avatars`, `upload_avatar`
- Inputs/Outputs:
  - Input: profile update payload or multipart image.
  - Output: `ProfileResponse` and avatar list response.

## `app/routes/v1/sessions.py`

- Purpose: session state retrieval/existence checks.
- Justification: frontend/session rehydration support.
- Internal logic:
  - fetch session snapshot.
  - normalize stored message/clarification payloads.
  - synthesize empty session response if absent.
- Connections:
  - `app/utils/session.py`
  - `app/models/responses.py`
- Key symbols:
  - `read_session`, `session_exists_route`
- Inputs/Outputs:
  - Input: session_id path parameter.
  - Output: `ChatSessionState` or `{exists: bool}`.

## `app/routes/v1/chat_mode.py`

- Purpose: post-recommendation follow-up chat endpoint.
- Justification: keeps conversational follow-ups separate from main query orchestration.
- Internal logic:
  - validate session and recommendation context.
  - build context package.
  - call chat follow-up service.
  - append conversation messages to session.
- Connections:
  - `app/services/chat_mode.py`
  - `app/utils/session.py`
- Key symbols:
  - `chat_mode_followup`
- Inputs/Outputs:
  - Input: `ChatModeRequest`.
  - Output: `ChatModeResponse`.

## `app/routes/v1/health.py`

- Purpose: provider/system health endpoint.
- Justification: runtime observability endpoint.
- Internal logic:
  - report configured/not-configured status for key providers.
  - probe Ollama and Redis with timeout.
- Connections:
  - `app/config/settings.py`
  - `redis.asyncio`, `httpx`
- Key symbols:
  - `health_check`
- Inputs/Outputs:
  - Input: none.
  - Output: `HealthResponse`.

## Service Layer

## `app/services/recommender.py`

- Purpose: category and product-type AI orchestration.
- Justification: provider-agnostic recommendation planning entrypoint.
- Internal logic:
  - normalize conversation context.
  - call providers in fallback order (Groq -> OpenAI -> Gemini -> Ollama).
  - retry per provider, return first valid payload.
- Connections:
  - all provider adapters under `app/providers/`.
- Key symbols:
  - `generate_category_plan`
  - `RecommendationServiceError`
- Inputs/Outputs:
  - Input: query/context/domain_hint.
  - Output: `CategoryReasoningResult`.

## `app/services/vagueness.py`

- Purpose: classify query as clear/vague/retry.
- Justification: prevents low-quality recommendation calls for under-specified requests.
- Internal logic:
  - provider fallback chain with retries.
  - parse model output into strict classification.
  - dynamic heuristic fallback if needed.
- Connections:
  - prompt module `app/prompts/vagueness_check.py`
  - dynamic analyzer service.
- Key symbols:
  - `classify_vagueness`
  - `VaguenessResult`
- Inputs/Outputs:
  - Input: raw query (+optional domain hint).
  - Output: `VaguenessResult` with classification and optional follow-up questions.

## `app/services/clarification.py`

- Purpose: clarification planning and sufficiency scoring.
- Justification: controlled question strategy for intent completion.
- Internal logic:
  - normalize Q/A pairs.
  - compute weighted coverage score by domain.
  - generate initial/additional follow-up questions.
  - decide next step.
- Connections:
  - dynamic analyzer/follow-up generator.
- Key symbols:
  - `ClarificationPlanner`
  - `plan_next_step`, `validate_sufficiency`
- Inputs/Outputs:
  - Input: query + clarification answers.
  - Output: sufficiency decision payload.

## `app/services/products.py`

- Purpose: product listing retrieval.
- Justification: isolates external product source behavior and fallback logic.
- Internal logic:
  - SerpAPI primary call for Google Shopping listings.
  - fallback to direct Google shopping search when SerpAPI fails.
  - URL normalization and affiliate-tag injection.
- Connections:
  - `app/config/settings.py`
  - `app/models/responses.py`
- Key symbols:
  - `fetch_products`
  - `_fetch_products_from_google`
  - `inject_affiliate_tag`
- Inputs/Outputs:
  - Input: product type/category and query context.
  - Output: list of `ProductCard` or `None`.

## `app/services/auth_csv.py`

- Purpose: CSV-backed auth persistence and credential validation.
- Justification: lightweight auth persistence for MVP stage.
- Internal logic:
  - normalize contact identifiers.
  - hash/verify password with PBKDF2.
  - read/write CSV rows under lock.
- Connections:
  - `app/models/responses.py`
  - settings for CSV path.
- Key symbols:
  - `CsvAuthService`
  - `signup`, `login`, `update_password`, `get_user_by_id`
- Inputs/Outputs:
  - Input: signup/login/update payload values.
  - Output: `AuthUser` or domain exceptions.

## `app/services/auth_token.py`

- Purpose: token issue and verification.
- Justification: stateless bearer auth without external identity provider.
- Internal logic:
  - create payload with sub/sid/iat/exp.
  - sign payload with HMAC SHA-256.
  - verify signature and expiry.
- Connections:
  - settings secret and TTL.
- Key symbols:
  - `create_auth_token`
  - `verify_auth_token`
- Inputs/Outputs:
  - Input: user_id/session_id or token string.
  - Output: token string or payload dict/None.

## `app/services/profile_store.py`

- Purpose: JSON-backed profile persistence.
- Justification: profile lifecycle without external DB dependency.
- Internal logic:
  - read/write profile map file under lock.
  - upsert default profile.
  - update fields, reset token metadata, avatar metadata.
- Connections:
  - settings path config.
- Key symbols:
  - `JsonProfileStore`
  - `UserProfile`
- Inputs/Outputs:
  - Input: user/profile fields.
  - Output: profile object/dict.

## `app/services/chat_mode.py`

- Purpose: answer post-recommendation follow-up questions.
- Justification: keeps contextual Q&A logic separate from main query orchestration.
- Internal logic:
  - flatten recommendation products from session payload.
  - heuristic domain-specific answer paths.
  - provider fallback answers if configured.
- Connections:
  - settings/provider endpoints.
- Key symbols:
  - `answer_chat_followup`
  - heuristic/provider helper functions.
- Inputs/Outputs:
  - Input: user question + context payload.
  - Output: assistant answer string.

## `app/services/vagueness.py`

- Purpose: classify query as `CLEAR`, `VAGUE`, or `RETRY`.
- Justification: routes under-specified queries into clarification before recommendation generation.
- Internal logic:
  - build prompt payload and execute provider fallback chain.
  - parse structured response and normalize follow-up questions.
  - fall back to dynamic analyzer when model output is ambiguous.
- Connections:
  - consumed by query route.
- Key symbols:
  - `classify_vagueness`
  - `VaguenessResult`
- Inputs/Outputs:
  - Input: query text.
  - Output: classification result with optional follow-up questions.

## `app/services/dynamic_intent_analyzer.py`

- Purpose: dynamic signal extraction and follow-up generation.
- Justification: domain-aware question generation without static templates only.
- Internal logic:
  - extract signals (price, environment, use-case, type, timeframe).
  - detect missing info.
  - generate contextual follow-up options.
- Connections:
  - used by clarification and vagueness services.
- Key symbols:
  - `DynamicIntentAnalyzer`
  - `DynamicFollowUpGenerator`
- Inputs/Outputs:
  - Input: query text.
  - Output: signal maps and question lists.

## Provider Layer

## `app/providers/base.py`

- Purpose: shared provider interfaces and normalized output models.
- Justification: enforce consistent output shape across provider adapters.
- Internal logic:
  - abstract provider class.
  - strict payload parsing/validation.
- Connections:
  - imported by all provider implementations and recommender service.
- Key symbols:
  - `BaseCategoryProvider`
  - `CategoryReasoningResult`
  - `RecommendedProductInfo`
  - provider exception types.
- Inputs/Outputs:
  - Input: provider raw payload dict.
  - Output: validated `CategoryReasoningResult`.

## `app/providers/groq_provider.py`, `openai_provider.py`, `gemini_provider.py`, `ollama_provider.py`

- Purpose: concrete provider adapters for category reasoning.
- Justification: isolate provider-specific API contracts and retries.
- Internal logic:
  - build messages from category prompt module.
  - execute provider API call.
  - parse model response JSON and validate via base parser.
- Connections:
  - settings for keys/models.
  - prompts for message construction.
  - provider base parser for normalized outputs.
- Key symbols:
  - provider classes: `GroqProvider`, `OpenAIProvider`, `GeminiProvider`, `OllamaProvider`.
- Inputs/Outputs:
  - Input: query/context.
  - Output: `CategoryReasoningResult`.

## Infrastructure And Utilities

## `app/config/settings.py`

- Purpose: typed runtime configuration.
- Justification: centralized env and defaults handling.
- Internal logic:
  - BaseSettings schema.
  - lenient list parsing.
  - optional provider model list loading from YAML.
- Connections:
  - consumed across core/services/providers/routes.
- Key symbols:
  - `Settings`, `get_settings`.
- Inputs/Outputs:
  - Input: env/.env values.
  - Output: settings singleton.

## `app/utils/session.py`

- Purpose: in-memory session state helpers.
- Justification: session continuity without DB dependency.
- Internal logic:
  - get/set/update/touch/delete operations under lock.
  - TTL eviction on access.
- Connections:
  - query/chat/auth/sessions routes.
- Key symbols:
  - `get_session`, `set_session`, `update_session`, `session_exists`, `touch_session`.
- Inputs/Outputs:
  - Input: session_id + dict payload.
  - Output: session snapshots.

## `app/utils/validators.py`

- Purpose: sanitize and guard against malformed/injection-like query input.
- Justification: guardrail before expensive provider calls.
- Internal logic:
  - query length checks.
  - regex pattern detection.
  - sanitization of null bytes/whitespace.
- Connections:
  - query route.
- Key symbols:
  - `sanitize_and_validate_query`.
- Inputs/Outputs:
  - Input: raw query string.
  - Output: sanitized query and validation result tuple.

## `app/core/middleware.py`, `app/core/logger.py`, `app/core/exceptions.py`, `app/core/security.py`, `app/core/auth.py`

- Purpose: cross-cutting concerns (observability, safety, auth dependency).
- Justification: isolate common concerns away from feature modules.
- Internal logic:
  - request logging and correlation IDs.
  - JSON log formatting + rotating file output.
  - HTTP exception and unhandled error handlers.
  - CORS policy and bearer-token user resolution.
- Connections:
  - all request paths pass through this layer.
- Inputs/Outputs:
  - Input: request lifecycle events and exception events.
  - Output: structured logs, standardized error payloads, authenticated user context.

