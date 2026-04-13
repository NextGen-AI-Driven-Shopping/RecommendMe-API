# Superseded Document

This file is retained for historical context. For current implementation-accurate backend documentation, use:
- backend_overview.md
- architecture.md
- api_reference.md
- data_flow.md
- ai_integration.md

---

# System Overview

## Purpose

RecommendMe API is a FastAPI backend that powers conversational recommendations.

At runtime, it performs four primary responsibilities:
- Accept conversational user input and session context.
- Determine whether the input is specific enough to recommend immediately.
- Generate recommendation structure (category and product types), then fetch product listings.
- Persist session/auth/profile state for continuity across requests.

## What The System Does

### Query Processing

- Validates and sanitizes user query input.
- Detects domain and intent using local heuristic classification.
- Runs vagueness classification through provider fallback logic.
- Returns either clarification questions or recommendations.

### Recommendation Generation

- Creates one session-level display category.
- Creates up to 10 product types with context-aware descriptions.
- Fetches product listings for each product type from SerpAPI.
- Falls back to direct Google Shopping fetch when SerpAPI is unavailable/failing.

### Session Continuity

- Stores session snapshots in memory.
- Provides hydration endpoints to retrieve latest state.
- Appends user/assistant messages during query and chat mode flows.

### Authentication And Profile Management

- Uses CSV-backed user authentication.
- Uses JSON-backed user profile persistence.
- Uses HMAC-signed bearer tokens for protected endpoints.

## Core Runtime Entry Points

- Root launcher: `main.py`
- Application factory and route mounting: `app/main.py`
- API namespace root: `app/routes/v1/router.py`

## External Integrations

- LLM providers: Groq, OpenAI, Gemini, Ollama.
- Product listing provider: SerpAPI (Google Shopping engine).
- Product fallback source: direct Google Shopping fetch.
- Optional health-probed dependency: Redis.

## Data Persistence Model

- Users: CSV file (`app/data/users.csv`)
- Profiles: JSON file (`app/data/profiles.json`)
- Sessions: in-process in-memory store (`app/utils/session.py`)
- Uploaded avatars: filesystem path configured by `PROFILE_UPLOAD_DIR`

## Service Boundaries

- API and orchestration logic: `app/routes`, `app/services`
- Provider adapters: `app/providers`
- Configuration and infra concerns: `app/config`, `app/core`, `app/utils`
- Contracts: `app/models`

## Operational Profile

Current implementation is optimized for single-instance or early-stage deployments.

Distributed-state behavior (shared session/cache persistence across multiple instances) is not implemented as a default runtime path.

