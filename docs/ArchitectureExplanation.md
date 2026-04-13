# Superseded Document

This file is retained for historical context. For current implementation-accurate backend documentation, use:
- backend_overview.md
- architecture.md
- api_reference.md
- data_flow.md
- ai_integration.md

---

# Architecture Explanation

## High-Level Architecture

`HTTP -> Routes -> Validation/Planning Services -> Provider Integrations -> Response + Session Snapshot`

The backend is organized as a layered architecture with clear module boundaries:

1. Transport layer
- FastAPI app and route handlers.

2. Domain/service layer
- Query planning, clarification logic, recommendation orchestration, product retrieval, auth/profile behavior.

3. Provider/integration layer
- LLM providers and external product data providers.

4. Infrastructure layer
- Settings, middleware, logging, security, session utilities, exceptions.

## Layer Responsibilities

## 1. Transport Layer

### Modules
- `app/main.py`
- `app/routes/v1/*.py`

### Responsibility
- Parse HTTP requests and dispatch to services.
- Bind request/response models to endpoint contracts.
- Enforce authentication dependencies for protected endpoints.

### Why It Exists
- Keeps protocol concerns isolated from business logic.

## 2. Service Layer

### Modules
- `app/services/*.py`

### Responsibility
- Implement business behavior for recommendation, auth, profiles, chat follow-up, and clarification planning.

### Why It Exists
- Centralizes domain logic in testable, composable units.

## 3. Provider Layer

### Modules
- `app/providers/*.py`

### Responsibility
- Normalize interactions with external LLM APIs.
- Convert provider-specific responses into a shared internal format.

### Why It Exists
- Prevents route/service code from depending on provider-specific protocols.

## 4. Infrastructure Layer

### Modules
- `app/config/settings.py`
- `app/core/*.py`
- `app/utils/*.py`

### Responsibility
- Configuration loading, middleware, security, logging, exception handling, utility helpers.

### Why It Exists
- Removes cross-cutting concerns from feature code.

## Dependency Direction

Allowed dependency direction:

- Routes -> Services -> Providers/Utils/Core
- Services -> Models/Providers/Utils/Config
- Providers -> Prompts/Config/Models

Avoided direction:
- Providers -> Routes
- Utils/Core -> Routes/Services (except generic helpers)

## Runtime Composition

At startup (`app/main.py`):
1. Cache cleanup runs.
2. FastAPI app is instantiated with lifespan hooks.
3. CORS middleware is configured.
4. request logging middleware is registered.
5. global exception handlers are registered.
6. v1 router is mounted.

## State Model

### Stateless Components
- Most request and provider logic is stateless per request.

### Stateful Components
- In-memory session store (`app/utils/session.py`)
- In-memory request deduplication cache (`app/main.py` -> `app.state.request_cache`)
- Optional in-memory product cache helpers (`app/services/cache.py`)

## Architectural Trade-Offs

1. CSV/JSON persistence is simple but not horizontally scalable.
2. In-memory session state is low-latency but process-local.
3. Provider fallback improves reliability but increases control-path complexity.
4. Bounded-concurrency product fetch keeps control flow predictable while reducing latency compared with full serial fetch.

