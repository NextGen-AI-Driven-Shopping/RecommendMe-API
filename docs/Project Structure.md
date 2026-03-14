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



Please Note Readmd.md file is already created keep it untouched