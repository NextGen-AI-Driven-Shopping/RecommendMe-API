# RecommendMe API

FastAPI backend for conversational shopping recommendations.

## Overview

The backend supports a full multi-turn recommendation flow:

1. Validate and sanitize user query input.
2. Run clarity classification (clear or follow-up needed).
3. Collect clarification answers (up to 5 total prompts).
4. Generate category plan using multi-provider AI fallback.
5. Fetch products primarily from SerpAPI.
6. Fall back to direct Google fetch only when SerpAPI fails or returns empty.
7. Persist session snapshots for progressive frontend rendering.

## Core Capabilities

- AI fallback chain for reasoning:
  - Groq
  - OpenAI
  - Gemini
  - Ollama (local fallback)
- Clarification planner with sufficiency scoring.
- Progressive recommendation snapshots during processing.
- Session hydration endpoint for frontend polling.
- CSV-based authentication and JSON-based profile storage.

## API Endpoints

### System

- GET /
- GET /health
- GET /v1/health

### Recommendation Flow

- POST /v1/query
- POST /v1/query/sufficiency_check
- GET /v1/sessions/{session_id}
- GET /v1/sessions/{session_id}/exists

### Auth and Profile

- POST /v1/auth/signup
- POST /v1/auth/login
- POST /v1/auth/forgot-password
- POST /v1/auth/reset-password
- GET /v1/auth/me
- GET /v1/profile
- POST /v1/profile
- PUT /v1/profile/update
- GET /v1/profile/avatars
- POST /v1/profile/avatar/upload

## Query Contract

Example request body for POST /v1/query:

```json
{
  "session_id": "optional-session-id",
  "user_message": "What should I buy for a first-time kitchen setup?",
  "conversation_history": [
    { "role": "user", "content": "What should I buy for a first-time kitchen setup?" }
  ],
  "clarification": [
    { "question": "How many people will you cook for?", "answer": "4-5" }
  ]
}
```

Recommendation responses use status = recommendations and include summary and categories.
Clarification responses use status = clarification_needed and include questions.

## Local Setup

1. Install dependencies.

```bash
pip install -r Requirements/requirements.txt
```

2. Optional dev dependencies.

```bash
pip install -r Requirements/requirements-dev.txt
```

3. Start API.

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Environment Variables

Core:

- APP_ENV
- DEBUG
- CORS_ORIGINS
- USERS_CSV_PATH
- PROFILE_STORE_PATH

Provider/API keys:

- GROQ_API_KEY
- OPENAI_API_KEY
- GEMINI_API_KEY
- SERPAPI_KEY

Model settings:

- GROQ_MODEL, GROQ_MODELS
- OPENAI_MODEL, OPENAI_MODELS
- GEMINI_MODEL, GEMINI_MODELS
- OLLAMA_URL, OLLAMA_MODEL, OLLAMA_MODELS

Optional:

- REDIS_URL
- AUTH_TOKEN_SECRET
- AUTH_TOKEN_TTL_MINUTES

## Tests

Run backend tests from project root:

```bash
pytest -q
```

## Additional Docs

- docs/api_architecture.md
- docs/ai_model_pipeline.md
- docs/project_structure.md
