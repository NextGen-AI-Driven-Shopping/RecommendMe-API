# Superseded Document

This file is retained for historical context. For current implementation-accurate backend documentation, use:
- backend_overview.md
- architecture.md
- api_reference.md
- data_flow.md
- ai_integration.md

---

# Configuration And Environment Setup

## Configuration Source Order

Settings are loaded by `app/config/settings.py` through `pydantic-settings`.

Source precedence:
1. Process environment variables.
2. `Environment/.env`.
3. `.env` at repository root.
4. Hardcoded defaults in `Settings` class.

## Environment Variable Behavior

## Core Runtime

| Variable | Default | Current Usage |
|---|---|---|
| `APP_NAME` | `RecommendMe API` | App metadata |
| `APP_ENV` | `development` | Login flow dev/prod behavior |
| `DEBUG` | `False` | Settings value available to runtime |

## AI Provider Keys And Models

| Variable | Default | Current Usage |
|---|---|---|
| `OPENAI_API_KEY` | empty | OpenAI provider and health checks |
| `OPENAI_MODEL` | `gpt-4o` | OpenAI model selection |
| `OPENAI_MODELS` | list default | OpenAI fallback model candidates |
| `GEMINI_API_KEY` | empty | Gemini provider and health checks |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Gemini model selection |
| `GEMINI_MODELS` | list default | Gemini fallback model candidates |
| `GROQ_API_KEY` | empty | Groq provider and health checks |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model selection |
| `GROQ_MODELS` | list default | Groq fallback model candidates |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama provider and health probes |
| `OLLAMA_MODEL` | `phi3` | Ollama model selection |
| `OLLAMA_MODELS` | list default | Ollama fallback model candidates |
| `AI_PROVIDER_CONFIG_PATH` | `app/config/provider_models.yml` | Model defaults YAML source |

## External Service And Security Settings

| Variable | Default | Current Usage |
|---|---|---|
| `SERPAPI_KEY` | empty | Product retrieval service |
| `REDIS_URL` | empty | Health probe route |
| `CORS_ORIGINS` | localhost list | CORS middleware |
| `CORS_ORIGIN_REGEX` | localhost regex | CORS middleware |

## Auth, Session, Storage

| Variable | Default | Current Usage |
|---|---|---|
| `AUTH_TOKEN_SECRET` | `recommendme-dev-secret-change-me` | Token signing/verification |
| `AUTH_TOKEN_TTL_MINUTES` | `10080` | Token expiry |
| `ALLOW_DEV_LOGIN_BYPASS` | `False` | Enables empty-credential dev login only when explicitly set in development |
| `USERS_CSV_PATH` | `app/data/users.csv` | CSV auth storage |
| `PROFILE_STORE_PATH` | `app/data/profiles.json` | Profile JSON storage |
| `PROFILE_UPLOAD_DIR` | `app/data/uploads/avatars` | Avatar upload path |
| `SESSION_TTL_MINUTES` | `30` | Defined in settings; session module currently uses fixed `1800s` constant |
| `RATE_LIMIT_PER_MINUTE` | `10` | Defined in settings; active enforcement not wired |
| `AFFILIATE_TAG` | empty | URL tagging in product service |
| `GROK_API_KEY` | empty | Not used outside settings |
| `OTHER_API_KEY` | empty | Not used outside settings |

## Setup Steps

## 1. Install dependencies

```bash
python -m pip install -r Requirements/requirements.txt
python -m pip install -r Requirements/requirements-dev.txt
```

## 2. Create environment file

Use either:
- `Environment/.env`
- or `.env` in repo root

Example minimal configuration:

```bash
APP_ENV=development
AUTH_TOKEN_SECRET=replace-with-unique-secret
GROQ_API_KEY=
OPENAI_API_KEY=
GEMINI_API_KEY=
SERPAPI_KEY=
CORS_ORIGINS=["http://localhost:5173","http://localhost:3000"]
```

## 3. Run backend

```bash
python -m uvicorn app.main:app --app-dir c:/Users/ksvar/Desktop/Genesis/RM/RecommendMe-API --host 127.0.0.1 --port 8000 --reload
```

## 4. Validate syntax

```bash
python -m compileall app
```

## 5. Run tests

```bash
python -m pytest -q tests
```

Current workspace state (2026-04-13): `50 passed`.

## Configuration Guidance

- Always override `AUTH_TOKEN_SECRET` in non-local environments.
- In production mode, startup fails if `AUTH_TOKEN_SECRET` is missing or left at default.
- Keep `ALLOW_DEV_LOGIN_BYPASS` disabled unless explicitly needed for local development.
- Keep API keys outside source control.
- Keep CORS allowlists explicit for deployed environments.
- Treat settings marked as unused in runtime as implementation backlog, not active controls.

