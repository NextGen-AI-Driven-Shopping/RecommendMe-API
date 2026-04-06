# RecommendMe API

FastAPI backend for the RecommendMe MVP.

## Overview

The API powers guided shopping conversations:
1. Detect whether a user query is clear or vague.
2. Ask structured follow-up questions when needed.
3. Extract categories and product plans with AI.
4. Fetch live product listings.
5. Return ranked, category-grouped recommendations.

## Key Features

- Tiered AI fallback for reasoning:
  - Groq (up to 4 models)
  - OpenAI (up to 4 models)
  - Gemini (up to 4 models)
- Clarification flow with max 5 questions (3 + optional 2)
- CSV-based authentication endpoints for MVP
- Live product enrichment via SerpAPI
- Structured response models with Pydantic

## Tech Stack

- FastAPI
- Pydantic v2
- httpx
- OpenAI SDK
- Optional Redis health probing

## API Endpoints

### System

- `GET /` - service welcome
- `GET /health` - lightweight liveness
- `GET /v1/health` - provider/service status

### Core

- `POST /v1/query` - clarification/recommendation orchestration
- `POST /v1/query/sufficiency_check` - clarification sufficiency scoring

### Authentication (MVP)

- `POST /v1/auth/signup`
- `POST /v1/auth/login`

## Request/Response Contract (Core)

`POST /v1/query` request:

```json
{
  "session_id": "optional-session-id",
  "user_message": "Need trekking gear for a 3-day trip",
  "conversation_history": [
    { "role": "user", "content": "Need trekking gear" }
  ],
  "clarification": [
    { "question": "What is your budget range?", "answer": "Under ₹5,000" }
  ]
}
```

Clarification response:

```json
{
  "status": "clarification_needed",
  "questions": [
    "What will you mainly use it for? Coding, gaming, editing, or general work?"
  ],
  "session_id": "..."
}
```

Recommendation response:

```json
{
  "status": "recommendations",
  "summary": "Top picks based on your context and budget.",
  "categories": [
    {
      "category": "Trekking Backpack",
      "tagline": "Top picks for trekking backpack",
      "why_needed": "Trekking Backpack is essential based on your context, constraints, and intended usage.",
      "products": []
    }
  ],
  "session_id": "..."
}
```

## Local Setup

1. Install dependencies:

```bash
pip install -r Requirements/requirements.txt
```

2. Optional dev tooling:

```bash
pip install -r Requirements/requirements-dev.txt
```

3. Run API:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Environment Variables

Core:

- `APP_ENV`
- `DEBUG`
- `CORS_ORIGINS`
- `USERS_CSV_PATH`

Provider keys:

- `GROQ_API_KEY`
- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- `SERPAPI_KEY`

Model selection:

- `GROQ_MODEL`, `GROQ_MODELS`
- `OPENAI_MODEL`, `OPENAI_MODELS`
- `GEMINI_MODEL`, `GEMINI_MODELS`

Optional:

- `REDIS_URL`
- `OLLAMA_URL`, `OLLAMA_MODEL` (health/probing compatibility)

## Tests

Run all backend tests from workspace root:

```bash
$env:PYTHONPATH='RecommendMe-API'; python -m pytest -q RecommendMe-API/tests
```

## Project Structure

See:

- `docs/api_architecture.md`
- `docs/ai_model_pipeline.md`
- `docs/LOGICAL_FLOW.md`
- `docs/project_structure.md`
