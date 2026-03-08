# RecommendMe — Backend API

The Python FastAPI backend for [RecommendMe](https://github.com/NextGen-AI-Driven-Shopping/recommendme) — a conversational AI product discovery engine.

> Handles everything the user never sees: query understanding, AI orchestration, product fetching, and response assembly.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green)
![License](https://img.shields.io/badge/License-MIT-purple)

---

## What This Repo Does

This is the brain of RecommendMe. Every user message flows through here. Responsibilities:

- **Query classification** — determines if the user's request has enough context to generate recommendations (Tier 1 AI via Ollama)
- **Follow-up generation** — if the query is vague, generates 2–3 targeted clarifying questions
- **Intent extraction** — once context is clear, identifies every product category the user needs (Tier 2 AI via GPT-4o)
- **Product fetching** — calls SerpAPI Google Shopping for real product listings
- **Ranking and explanation** — uses GPT-4o to rank the top 3 products per category with personalized reasons
- **Response assembly** — packages everything into a clean, structured JSON response for the frontend

The frontend (`recommendme-ui`) only talks to one endpoint: `POST /v1/query`. Everything else is internal.

---

## Architecture

```
Incoming Request (POST /v1/query)
            │
            ▼
┌───────────────────────┐
│   FastAPI Route       │  app/api/v1/query.py
│   Validate input      │  ← Pydantic schema check
│   Resolve session ID  │  ← app/utils/session.py
└──────────┬────────────┘
           │
           ▼
┌───────────────────────┐
│   Vagueness Service   │  app/services/vagueness.py
│   Tier 1 AI — Ollama  │  ← Phi-3 Mini (local)
│   Is query CLEAR?     │  ← Falls back to GPT-4o-mini
└──────────┬────────────┘
           │
     VAGUE │ CLEAR
     ┌─────┘  └──────────────────────────┐
     ▼                                   ▼
Return follow-up              ┌───────────────────────┐
questions to frontend         │  Recommender Service  │  app/services/recommender.py
                              │  Tier 2 AI — GPT-4o   │
                              │  Extract intent        │
                              │  Generate categories   │
                              └──────────┬────────────┘
                                         │
                                         ▼
                              ┌───────────────────────┐
                              │  Product Service      │  app/services/products.py
                              │  SerpAPI fetch        │  ← Per category
                              │  Cache check first    │  ← app/services/cache.py
                              └──────────┬────────────┘
                                         │
                                         ▼
                              ┌───────────────────────┐
                              │  Ranking Service      │  app/services/ranking.py
                              │  GPT-4o ranks top 3   │
                              │  Writes reasons       │
                              └──────────┬────────────┘
                                         │
                                         ▼
                              ┌───────────────────────┐
                              │  Response Assembly    │  app/utils/formatters.py
                              │  Structured JSON      │
                              │  Returned to frontend │
                              └───────────────────────┘
```

---

## Two-Tier AI Design

| | Tier 1 | Tier 2 |
|---|---|---|
| **Model** | Ollama — Phi-3 Mini | OpenAI GPT-4o |
| **Runs on** | Local server | OpenAI Cloud API |
| **Job** | Classify query as CLEAR or VAGUE. Generate follow-up questions if vague. | Extract intent. Generate product categories. Rank and explain top products. |
| **Cost** | Free | ~$0.01–$0.03 per session |
| **Speed** | < 1.5s | < 4s |
| **Fallback** | GPT-4o-mini if Ollama unavailable | — |

---

## Project Structure

```
recommendme-api/
│
├── app/                                    ← Main application package
│   ├── __init__.py
│   ├── main.py                             ← FastAPI app, lifespan, middleware registration
│   │
│   ├── api/                                ← All route handlers
│   │   ├── __init__.py
│   │   ├── deps.py                         ← Shared dependencies (session, rate limiter injection)
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py                   ← Aggregates all v1 routes into one router
│   │       ├── query.py                    ← POST /v1/query  (core endpoint)
│   │       └── health.py                   ← GET /v1/health  (system status)
│   │
│   ├── services/                           ← Business logic — one job per file
│   │   ├── __init__.py
│   │   ├── vagueness.py                    ← Tier 1 AI: Ollama check + GPT-4o-mini fallback
│   │   ├── recommender.py                  ← Tier 2 AI: GPT-4o intent + category generation
│   │   ├── products.py                     ← SerpAPI fetch + affiliate tag injection
│   │   ├── ranking.py                      ← GPT-4o product ranking + explanation generation
│   │   └── cache.py                        ← Redis get/set for product query results
│   │
│   ├── models/                             ← All Pydantic models, split by purpose
│   │   ├── __init__.py
│   │   ├── requests.py                     ← QueryRequest, ConversationMessage
│   │   ├── responses.py                    ← QueryResponse, ProductCard, CategoryResult
│   │   └── internal.py                     ← Internal types not exposed to API consumers
│   │
│   ├── prompts/                            ← AI prompt templates, versioned and isolated
│   │   ├── __init__.py
│   │   ├── vagueness_check.py              ← Tier 1 prompt: CLEAR / VAGUE classification
│   │   ├── intent_extraction.py            ← Tier 2 prompt: extract categories from context
│   │   └── product_ranking.py              ← Tier 2 prompt: rank products + write reasons
│   │
│   ├── core/                               ← App config, exceptions, cross-cutting concerns
│   │   ├── __init__.py
│   │   ├── config.py                       ← All settings loaded from .env via Pydantic BaseSettings
│   │   ├── exceptions.py                   ← Custom exception classes + HTTP error handlers
│   │   ├── logger.py                       ← Structured JSON logging setup
│   │   ├── middleware.py                   ← Request logging, timing, correlation ID middleware
│   │   └── security.py                     ← Input sanitization, CORS config, rate limit rules
│   │
│   └── utils/                              ← Stateless helper functions
│       ├── __init__.py
│       ├── session.py                      ← In-memory session store (dict keyed by session_id)
│       ├── validators.py                   ← Query length checks, injection pattern detection
│       └── formatters.py                   ← Response assembly, affiliate URL tagging
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                         ← Shared pytest fixtures, mock clients, test app setup
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_vagueness.py
│   │   ├── test_recommender.py
│   │   ├── test_products.py
│   │   ├── test_ranking.py
│   │   ├── test_prompts.py
│   │   ├── test_validators.py
│   │   └── test_formatters.py
│   └── integration/
│       ├── __init__.py
│       ├── test_query_flow.py              ← Full flow: vague → follow-up → recommendations
│       └── test_health.py
│
├── scripts/                                ← Developer utilities, not part of the app
│   ├── test_prompt.py                      ← Run a prompt against GPT-4o from terminal
│   ├── mock_serp.py                        ← Generate mock SerpAPI responses for offline dev
│   └── check_ollama.py                     ← Verify Ollama is running and model is loaded
│
├── .github/
│   └── workflows/
│       ├── ci.yml                          ← Run tests + lint on every PR
│       └── deploy.yml                      ← Auto-deploy to Railway on merge to main
│
├── main.py                                 ← Entry point: imports and runs app from app/
├── requirements.txt                        ← Production dependencies
├── requirements-dev.txt                    ← Dev + test dependencies
├── .env.example                            ← All env vars documented with placeholder values
├── .gitignore
├── Dockerfile                              ← Production container
├── docker-compose.yml                      ← Local dev: app + Redis together
└── README.md
```

---

## API Reference

### Base URL

```
Production:   https://api.recommendme.in/v1
Development:  http://localhost:8000/v1
```

---

### `POST /v1/query`

The primary endpoint. Accepts a user message and conversation history. Returns either follow-up questions or final product recommendations.

**Request**

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_message": "I want to go trekking",
  "conversation_history": [
    { "role": "user", "content": "I want to go trekking" }
  ]
}
```

**Response A — Query is vague**

```json
{
  "type": "followup",
  "questions": [
    "Where are you trekking and for how many days?",
    "Will you be camping or staying in hotels?",
    "What is your approximate budget?"
  ]
}
```

**Response B — Context is clear**

```json
{
  "type": "recommendations",
  "summary": "Gear for a 3-day Himalayan camping trek under ₹15,000.",
  "categories": [
    {
      "name": "Tent",
      "why_needed": "Essential for camping in open terrain.",
      "budget_allocation": "₹3,000 – ₹6,000",
      "products": [
        {
          "title": "Quechua 2-Person Tent MH100",
          "price": "₹3,499",
          "rating": 4.5,
          "reviews": "2,140",
          "source": "Decathlon",
          "link": "https://decathlon.in/...",
          "thumbnail": "https://...",
          "reason": "Best weight-to-price ratio for Himalayan conditions."
        }
      ],
      "expert_tip": "Look for a double-wall tent for better rain protection."
    }
  ]
}
```

---

### `GET /v1/health`

Returns system health including AI service availability.

**Response**

```json
{
  "status": "ok",
  "ollama": "available",
  "openai": "connected",
  "serpapi": "configured"
}
```

---

## Error Responses

All errors return a consistent structure:

```json
{
  "error": true,
  "code": "OPENAI_RATE_LIMIT",
  "message": "Our AI is momentarily busy. Please try again in a few seconds.",
  "retry_after": 5
}
```

| Error Code | Trigger | HTTP Status |
|------------|---------|-------------|
| `QUERY_TOO_SHORT` | Query under 3 words | 400 |
| `OLLAMA_UNAVAILABLE` | Ollama not running | Silent fallback |
| `OPENAI_RATE_LIMIT` | 429 from OpenAI | 429 |
| `SERP_NO_RESULTS` | Empty SerpAPI results | 200 (partial) |
| `SERP_QUOTA_EXCEEDED` | SerpAPI limit reached | 503 |
| `SESSION_EXPIRED` | Inactive > 30 min | 401 |
| `INTERNAL_ERROR` | Unhandled exception | 500 |

---

## Getting Started

### Prerequisites

- Python 3.11+
- pip
- Ollama installed locally (optional but recommended)
- OpenAI API key
- SerpAPI key (optional — mock data used without it)

### 1. Clone and Install

```bash
git clone https://github.com/NextGen-AI-Driven-Shopping/recommendme-api.git
cd recommendme-api

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
pip install -r requirements-dev.txt    # for testing + linting
```

### 2. Environment Variables

```bash
cp .env.example .env
```

Open `.env` and fill in:

```env
# Required
OPENAI_API_KEY=sk-...

# Optional — mock data used if not set
SERPAPI_KEY=...

# Optional — fallback to GPT-4o-mini if Ollama not running
OLLAMA_URL=http://localhost:11434/api/generate
OLLAMA_MODEL=phi3

# App config
APP_ENV=development
RATE_LIMIT_PER_MINUTE=10
SESSION_TTL_MINUTES=30
```

### 3. Set Up Ollama (Optional)

```bash
# Install from https://ollama.com then run:
ollama pull phi3
```

Ollama runs at `http://localhost:11434`. If it's not running, the app silently falls back to GPT-4o-mini — nothing breaks.

### 4. Run with Docker (Recommended)

```bash
docker-compose up --build
```

Starts the FastAPI backend and Redis together. No manual Redis setup needed.

### 5. Run without Docker

```bash
uvicorn main:app --reload
```

Server at `http://localhost:8000`

API docs:
- Swagger UI → `http://localhost:8000/docs`
- ReDoc → `http://localhost:8000/redoc`

---

## Running Tests

```bash
# Run all tests
pytest

# With coverage report
pytest --cov=app --cov-report=term-missing

# Unit tests only
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v

# Specific file
pytest tests/unit/test_vagueness.py -v
```

---

## Linting

```bash
# Check for issues
ruff check .

# Auto-fix where possible
ruff check . --fix
```

---

## Security

- All API keys loaded from environment variables — never hardcoded
- `.env` is in `.gitignore` — never committed
- User input validated and sanitized before passing to any AI model
- Conversation history capped at 20 messages per session (prompt injection protection)
- Rate limiting via `slowapi` — 10 requests/minute per IP on `POST /v1/query`
- CORS restricted to whitelisted frontend origin in production
- HTTPS enforced in production

---

## Deployment

### Deploy to Railway

```bash
npm install -g @railway/cli
railway login
railway init
railway up
```

Set all environment variables in the Railway dashboard under **Variables**.

### Deploy to Render

Connect your GitHub repo to Render and set the start command to:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

Add all environment variables under **Environment** in the Render dashboard.

> **Note:** Ollama cannot run on free-tier Railway or Render instances due to RAM constraints. The app automatically falls back to GPT-4o-mini in production — no action needed.

---

## Key Design Decisions

**`app/` package over root-level structure.** All application code lives inside `app/` to create a clean boundary between the running application, tests, and scripts. Avoids import collisions, simplifies the Dockerfile, and makes team ownership boundaries obvious.

**Stateless backend.** No database in MVP. Session state lives in-memory as a Python dictionary keyed by `session_id`. Keeps deployment simple and enables horizontal scaling. A database becomes relevant in v2 when user accounts and history are added.

**Prompts are code, not strings.** All AI prompts live in `app/prompts/` as structured Python files, not scattered inline strings. Independently testable, versionable, and improvable without touching service logic.

**Ranking is its own service.** `ranking.py` is split from `products.py` deliberately. Fetching is I/O bound (SerpAPI network call), ranking is AI bound (GPT-4o). Separating them makes each independently testable and swappable without touching the other.

**Ollama is optional by design.** The two-tier AI setup saves money at scale, but Ollama requires RAM that free hosting tiers don't provide. The fallback to GPT-4o-mini ensures the app runs identically in all environments.

**One endpoint.** The entire conversation flow runs through `POST /v1/query`. The `type` field in the response (`followup` or `recommendations`) tells the frontend what to render. Keeps the API contract minimal and frontend logic clean.

---

## Dependencies

**Production** (`requirements.txt`)

```
fastapi           — API framework
uvicorn           — ASGI server
pydantic          — Request/response validation
pydantic-settings — Config loading from .env
httpx             — Async HTTP client (Ollama + SerpAPI)
openai            — Official OpenAI Python SDK
python-dotenv     — Environment variable loading
slowapi           — Rate limiting middleware
redis             — Redis client for caching
```

**Development** (`requirements-dev.txt`)

```
pytest            — Testing framework
pytest-asyncio    — Async test support
pytest-cov        — Coverage reporting
httpx             — TestClient for FastAPI route testing
ruff              — Linting and formatting
```

---

## Team Ownership

| Member | Owns |
|--------|------|
| Project Lead | `main.py`, `.github/workflows/`, `Dockerfile`, `docker-compose.yml` — overall system integration, system architecture decisions, SDLC planning and supervision, project maintenance, GitHub organization management, repository structure management, CI/CD pipeline monitoring, code reviews and quality enforcement, partial testing coordination, feature planning and enhancements, dependency and version management, project monitoring and progress tracking, release planning and versioning, deployment oversight, technical decision making, issue prioritization and bug triage, documentation oversight, performance and scalability review |
| API Layer | `app/api/` — all files |
| Vagueness Service | `app/services/vagueness.py`, `app/prompts/vagueness_check.py` |
| Recommendation Service | `app/services/recommender.py`, `app/prompts/intent_extraction.py` |
| Ranking Service | `app/services/ranking.py`, `app/prompts/product_ranking.py` |
| Product & Data Service | `app/services/products.py`, `app/utils/formatters.py` |
| Prompt Engineer | `app/prompts/` — all files, `scripts/test_prompt.py` |
| Core & Config | `app/core/` — all files |
| Models & Validation | `app/models/`, `app/utils/validators.py`, `app/utils/session.py` |
| Cache & Performance | `app/services/cache.py` |
| Testing | `tests/` — all files, `requirements-dev.txt` |


---

## Contributing

Read the org-wide [CONTRIBUTING.md](https://github.com/NextGen-AI-Driven-Shopping/.github/blob/main/CONTRIBUTING.md) before submitting a PR.

For backend-specific work — follow PEP 8, use type hints on all functions, keep each service focused on one job, and write tests for anything you add or change.

---

## License

MIT © [NextGen AI-Driven Shopping](https://github.com/NextGen-AI-Driven-Shopping)
