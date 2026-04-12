# API Architecture

## Purpose

This document explains how the backend API is organized, how requests traverse the system, and where responsibilities are separated.

## Versioning Model

- Versioned HTTP routes are mounted under `/v1` via `app/routes/v1/router.py`.
- Root-level non-versioned routes (`/`, `/health`) are defined in `app/main.py`.

## Layered API Design

## HTTP Layer (`app/routes/v1`)

Responsibilities:
- Validate and bind request models.
- Invoke service-layer logic.
- Return typed response models.

Why this layer exists:
- Keeps transport concerns isolated from domain logic.

## Service Layer (`app/services`)

Responsibilities:
- Clarification planning.
- Recommendation planning.
- Product retrieval.
- Auth/profile operations.
- Chat follow-up behavior.

Why this layer exists:
- Concentrates business logic in modules reusable across routes.

## Provider Layer (`app/providers`)

Responsibilities:
- External LLM API calls.
- Provider-specific retries and response normalization.

Why this layer exists:
- Encapsulates provider protocol differences behind one internal contract.

## Supporting Infrastructure (`app/core`, `app/config`, `app/utils`)

Responsibilities:
- Security and auth dependency wiring.
- Middleware and request correlation.
- Exception normalization.
- Settings and utility helpers.

Why this layer exists:
- Avoids cross-cutting behavior being duplicated inside route/service modules.

## Endpoint Topology

- Query endpoints: `POST /v1/query`, `POST /v1/query/sufficiency_check`
- Session endpoints: `GET /v1/sessions/{session_id}`, `GET /v1/sessions/{session_id}/exists`
- Chat endpoint: `POST /v1/chat/mode`
- Auth endpoints: `/v1/auth/*`
- Profile endpoints: `/v1/profile*`
- Health endpoint: `GET /v1/health`

## Contract Types

Input contracts (`app/models/requests.py`):
- Query, sufficiency, auth, profile update, chat mode.

Output contracts (`app/models/responses.py`):
- Query response variants, health, auth/profile payloads, session/chat state.

## State And Persistence

- Auth users persisted in CSV.
- Profiles persisted in JSON.
- Sessions held in memory with TTL.

Architecture implication:
- Current persistence model is simple and local-process oriented.

## API Reliability Behavior

- Provider fallback chain for recommendation planning.
- Product retrieval fallback from SerpAPI to direct Google fetch.
- Degraded response signaling through `QueryResponse.data_source` and `QueryResponse.degraded`.

## Security Boundaries

Protected by bearer dependency:
- `GET /v1/auth/me`
- `GET/POST /v1/profile`
- `PUT /v1/profile/update`
- `POST /v1/profile/avatar/upload`

Public endpoints remain token-free by design.
