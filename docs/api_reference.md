# API Reference

## Base
- Local dev default: `http://127.0.0.1:8000`
- Versioned prefix: `/v1`
- Content type: `application/json` unless multipart endpoint noted.

## Error Envelope
Most failures return:

```json
{
  "detail": "Human-readable message"
}
```

Unhandled server errors return:

```json
{
  "detail": "An internal server error occurred."
}
```

## System Endpoints

### `GET /`
- Purpose: service welcome metadata.
- Auth: public.
- Response 200:

```json
{
  "message": "Welcome to RecommendMe API",
  "status": "✅ Server is running",
  "version": "1.0.0",
  "documentation": "/docs",
  "health_check": "/health"
}
```

### `GET /health`
- Purpose: lightweight liveness probe.
- Auth: public.
- Response 200:

```json
{ "status": "ok" }
```

### `GET /v1/health`
- Purpose: dependency/config status snapshot.
- Auth: public.
- Response 200 (`HealthResponse`):

```json
{
  "status": "ok",
  "openai": "configured",
  "gemini": "configured",
  "groq": "configured",
  "serpapi": "configured",
  "ollama": "healthy",
  "redis": "not configured"
}
```

Possible values per provider field:
- `configured` / `not configured` for key-based services.
- `healthy`, `unhealthy`, `timeout`, `unreachable` for probed services.

## Query Pipeline Endpoint

### `POST /v1/query`
- Purpose: run recommendation flow (validation -> classification -> clarification -> recommendations).
- Auth: public.
- Request body (`QueryRequest`):

```json
{
  "user_message": "Need trekking shoes for monsoon",
  "session_id": "optional-session-id",
  "request_id": "optional-dedup-id",
  "conversation_history": [
    { "role": "user", "content": "..." },
    { "role": "assistant", "content": "..." }
  ],
  "clarification": [
    { "question": "...", "answer": "..." }
  ],
  "clarification_round": 1
}
```

Field constraints:
- `user_message`: 3..500 chars (then additional validator checks).
- `conversation_history`: max 30 messages.
- `clarification_round`: `0`, `1`, `2`, or omitted.

#### Response modes (`QueryResponse`)

1. `pre_clarification`

```json
{
  "status": "pre_clarification",
  "message": "What type of trip are you planning?",
  "questions": [
    {
      "question": "What type of trip are you planning?",
      "options": ["Trek", "Road trip", "Business travel"]
    }
  ],
  "clarification_round": 0,
  "asked_questions": 0,
  "max_total_questions": 5,
  "session_id": "..."
}
```

2. `clarification_needed`

```json
{
  "status": "clarification_needed",
  "message": "• Where will you trek?\n• How long is the trek?\n• What weather do you expect?",
  "questions": [
    { "question": "Where will you trek?", "options": ["Forest", "Mountain"] }
  ],
  "clarification_round": 1,
  "asked_questions": 0,
  "max_total_questions": 5,
  "session_id": "..."
}
```

3. `recommendations`

```json
{
  "status": "recommendations",
  "category": "Monsoon Trekking Gear",
  "summary": "Here are my recommendations based on your requirements.",
  "product_types": [
    {
      "product_type": "Waterproof Trekking Shoes",
      "description": "...",
      "product_items": [
        {
          "product_name": "...",
          "image_url": "...",
          "price_inr": "₹3,499",
          "short_description": "...",
          "buy_link": "...",
          "rating": 4.4,
          "brand": "...",
          "reviews_count": 320,
          "delivery_info": "...",
          "availability": null,
          "source": "..."
        }
      ],
      "serp_error": false,
      "serp_error_message": null
    }
  ],
  "session_id": "..."
}
```

4. `out_of_scope`

```json
{
  "status": "out_of_scope",
  "message": "I'm a product recommendation assistant...",
  "session_id": "..."
}
```

#### Error responses
- `422`: query failed validation (`ValidationException`).
- `503`: AI provider failures in classification/question/recommendation stages.
- `500`: unexpected server failure.

## Session Endpoints

### `GET /v1/sessions/{session_id}`
- Purpose: hydrate or create frontend chat state.
- Auth: public.
- Behavior:
  - If session not found: returns synthetic `new` state with timestamps.
  - If found: returns stored snapshot and touches TTL.

Response 200 (`ChatSessionState`) example:

```json
{
  "session_id": "abc",
  "status": "clarification_needed",
  "title": "Need monsoon trekking shoes",
  "user_id": "optional-user-id",
  "messages": [],
  "created_at": "2026-04-13T10:00:00+00:00",
  "updated_at": "2026-04-13T10:05:00+00:00",
  "original_query": "...",
  "pending_questions": [],
  "clarification_round": 1,
  "clarification_answers": [],
  "latest_response": null
}
```

### `GET /v1/sessions/{session_id}/exists`
- Purpose: check if non-expired session exists.
- Auth: public.
- Response 200:

```json
{ "exists": true }
```

## Chat Mode

### `POST /v1/chat/mode`
- Purpose: follow-up Q&A after recommendations are already generated.
- Auth: public.
- Request body (`ChatModeRequest`):

```json
{
  "session_id": "...",
  "user_message": "Which one is better for heavy rain?"
}
```

- Success response 200 (`ChatModeResponse`):

```json
{
  "session_id": "...",
  "message": "Based on the listed products..."
}
```

- Errors:
  - `404`: session not found.
  - `400`: session exists but no recommendation context.

## Auth Endpoints

### `POST /v1/auth/signup`
- Auth: public.
- Request (`SignupRequest`):

```json
{
  "username": "john",
  "first_name": "John",
  "last_name": "Doe",
  "email": "john@example.com",
  "phone": "+919999999999",
  "password": "secret123",
  "session_id": "optional-session"
}
```

- Success 200 (`AuthSignupResponse`) includes `message`, `token`, `user`, `session_id`, `profile`.
- Errors:
  - `400`: validation (contact/password rules).
  - `409`: duplicate email/phone.

### `POST /v1/auth/login`
- Auth: public.
- Request (`LoginRequest`):

```json
{
  "identifier": "john@example.com",
  "password": "secret123",
  "session_id": "optional-session"
}
```

- Success 200 (`AuthLoginResponse`) with token and profile.
- Errors:
  - `400`: malformed input.
  - `404`: user not found.
  - `401`: password mismatch.

### `POST /v1/auth/forgot-password`
- Auth: public.
- Request:

```json
{ "identifier": "john@example.com" }
```

- Success 200 always.
  - Non-prod: returns generated `reset_token` for development.
  - Prod: generic message only.

### `POST /v1/auth/reset-password`
- Auth: public.
- Request:

```json
{
  "reset_token": "...",
  "new_password": "newSecret123"
}
```

- Success 200: password reset confirmation.
- Errors:
  - `404`: token not found/expired.

### `GET /v1/auth/me`
- Auth: bearer required.
- Response 200:

```json
{
  "user": {
    "user_id": "...",
    "username": "...",
    "first_name": "...",
    "last_name": "...",
    "email": "...",
    "phone": "...",
    "created_at": "..."
  },
  "session_id": "optional-session-id-from-token"
}
```

- Errors:
  - `401`: missing/invalid/expired token or user no longer exists.

## Profile Endpoints

### `GET /v1/profile`
- Auth: bearer required.
- Returns `ProfileResponse`.

### `POST /v1/profile`
- Auth: bearer required.
- Purpose: create/update profile fields.
- Body (`ProfileUpdateRequest`) partial-update style:

```json
{
  "username": "johnny",
  "gender": "Male",
  "age": 27,
  "interests": ["trekking", "camping"],
  "about": "Weekend hiker",
  "avatar_url": "https://..."
}
```

### `PUT /v1/profile/update`
- Auth: bearer required.
- Same request/response shape as profile `POST`.

### `GET /v1/profile/avatars`
- Auth: public.
- Returns predefined avatar list.

### `POST /v1/profile/avatar/upload`
- Auth: bearer required.
- Content type: multipart/form-data (`image` file part).
- Constraints:
  - MIME: `image/jpeg`, `image/png`, `image/webp`
  - Max size: 2 MB
- Response: updated `ProfileResponse`.
- Errors:
  - `400`: invalid type or oversized file.
  - `404`: profile missing.

## Implemented Endpoint Inventory (Authoritative)
- `GET /`
- `GET /health`
- `GET /v1/health`
- `POST /v1/query`
- `GET /v1/sessions/{session_id}`
- `GET /v1/sessions/{session_id}/exists`
- `POST /v1/chat/mode`
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

No `POST /v1/query/sufficiency_check` route is currently implemented.
