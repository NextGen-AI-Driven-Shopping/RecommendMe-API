# RecommendMe — Backend API

The Python FastAPI backend for [RecommendMe](https://github.com/NextGen-AI-Driven-Shopping/recommendme) — a conversational AI product discovery engine.

> Handles everything the user never sees: query understanding, AI orchestration, product fetching, and response assembly.

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
│   FastAPI Route       │  routes/query.py
│   Validate input      │  ← Pydantic schema check
│   Generate session ID │
└──────────┬────────────┘
           │
           ▼
┌───────────────────────┐
│   Vagueness Service   │  services/vagueness.py
│   Tier 1 AI — Ollama  │  ← Phi-3 Mini (local)
│   Is query CLEAR?     │  ← Falls back to GPT-4o-mini
└──────────┬────────────┘
           │
     VAGUE │ CLEAR
     ┌─────┘  └──────────────────────────┐
     ▼                                   ▼
Return follow-up              ┌───────────────────────┐
questions to frontend         │  Recommender Service  │  services/recommender.py
                              │  Tier 2 AI — GPT-4o   │
                              │  Extract intent        │
                              │  Generate categories   │
                              └──────────┬────────────┘
                                         │
                                         ▼
                              ┌───────────────────────┐
                              │  Product Service      │  services/products.py
                              │  SerpAPI fetch        │  ← Per category
                              │  GPT-4o ranking       │  ← Top 3 with reasons
                              └──────────┬────────────┘
                                         │
                                         ▼
                              ┌───────────────────────┐
                              │  Structured Response  │
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
├── main.py                        ← FastAPI app entry point, middleware, CORS
├── requirements.txt               ← All Python dependencies
├── .env.example                   ← Environment variable template
├── .gitignore
├── README.md
│
├── routes/
│   ├── __init__.py
│   ├── query.py                   ← POST /v1/query  (core endpoint)
│   └── health.py                  ← GET /v1/health  (status check)
│
├── services/
│   ├── __init__.py
│   ├── vagueness.py               ← Tier 1 AI: Ollama vagueness check + fallback
│   ├── recommender.py             ← Tier 2 AI: GPT-4o intent extraction + categories
│   └── products.py                ← SerpAPI product fetch + GPT-4o ranking
│
├── models/
│   ├── __init__.py
│   └── schemas.py                 ← All Pydantic request/response models
│
├── prompts/
│   ├── vagueness_check.py         ← Tier 1 prompt template
│   ├── intent_extraction.py       ← Tier 2 prompt: category generation
│   └── product_ranking.py         ← Tier 2 prompt: rank + explain products
│
├── core/
│   ├── __init__.py
│   ├── config.py                  ← App settings loaded from .env
│   ├── exceptions.py              ← Custom exception classes
│   └── logger.py                  ← Structured logging setup
│
└── tests/
    ├── __init__.py
    ├── test_vagueness.py          ← Unit tests for vagueness classifier
    ├── test_recommender.py        ← Unit tests for recommendation logic
    ├── test_products.py           ← Unit tests for product fetching
    └── test_routes.py             ← Integration tests for API endpoints
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

Ollama runs automatically at `http://localhost:11434`. If it's not running, the app silently falls back to GPT-4o-mini — nothing breaks.

### 4. Run the Server

```bash
uvicorn main:app --reload
```

Server runs at `http://localhost:8000`

Auto-generated API docs available at:
- Swagger UI → `http://localhost:8000/docs`
- ReDoc → `http://localhost:8000/redoc`

---

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=. --cov-report=term-missing

# Run a specific test file
pytest tests/test_vagueness.py -v
```

---

## Security

- All API keys loaded from environment variables via `python-dotenv` — never hardcoded
- `.env` is in `.gitignore` — never committed
- User input validated and sanitized before passing to any AI model
- Conversation history capped at 20 messages per session (prompt injection protection)
- Rate limiting via `slowapi` — 10 requests/minute per IP on `POST /v1/query`
- CORS restricted to whitelisted frontend origin in production
- HTTPS enforced in production

---

## Deployment

The backend is deployed on **Railway** or **Render**.

### Deploy to Railway

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and deploy
railway login
railway init
railway up
```

Set all environment variables in the Railway project dashboard under **Variables**.

### Deploy to Render

Connect your GitHub repo to Render, set the start command to:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

Add all environment variables in the Render dashboard under **Environment**.

> **Note:** Ollama cannot run on Render or Railway free tiers due to RAM constraints. The app automatically falls back to GPT-4o-mini in production — no action needed.

---

## Key Design Decisions

**Stateless backend.** No database in MVP. Session state lives in-memory as a Python dictionary keyed by `session_id`. This keeps deployment simple and enables horizontal scaling. A database becomes relevant in v2 when user accounts and history are added.

**Prompts are code, not strings.** All AI prompts live in `prompts/` as structured Python files, not scattered inline strings. This makes them easy to version, test, and improve independently of the service logic.

**Ollama is optional by design.** The two-tier AI setup saves money at scale, but Ollama requires server RAM that free hosting tiers don't always provide. The fallback to GPT-4o-mini ensures the app works identically in all environments.

**One endpoint.** The entire conversation flow runs through `POST /v1/query`. The response `type` field (`followup` or `recommendations`) tells the frontend what to render. This keeps the API contract simple and the frontend logic clean.

---

## Dependencies

```
fastapi          — API framework
uvicorn          — ASGI server
pydantic         — Request/response validation
httpx            — Async HTTP client (Ollama + SerpAPI calls)
openai           — Official OpenAI Python SDK
python-dotenv    — Environment variable loading
slowapi          — Rate limiting middleware
pytest           — Testing framework
pytest-asyncio   — Async test support
pytest-cov       — Coverage reporting
```

---

## Related Repos

| Repo | Description |
|------|-------------|
| [`recommendme-ui`](https://github.com/NextGen-AI-Driven-Shopping/recommendme-ui) | React frontend |
| [`prompt-library`](https://github.com/NextGen-AI-Driven-Shopping/prompt-library) | AI prompts |
| [`docs`](https://github.com/NextGen-AI-Driven-Shopping/docs) | SDD, architecture, full documentation |

---

## License

MIT © [NextGen AI-Driven Shopping](https://github.com/NextGen-AI-Driven-Shopping)
