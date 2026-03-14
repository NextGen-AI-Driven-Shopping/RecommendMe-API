# API System Documentation

## Who This API Is For

- Developers integrating shopping recommendation APIs into third-party apps.
- Frontend services that need one stable endpoint for multi-step AI workflows.
- AI workflow consumers that require structured responses and provider fallback reliability.

## API Design Principles

- Modular architecture: transport, orchestration, prompts, and providers are separated.
- Separation of concerns: route handlers coordinate, services decide, providers execute.
- Provider abstraction: Gemini, GROQ, OpenAI, and Ollama share one interface.
- Fallback reliability: category reasoning falls back in deterministic order.
- Stateless API design: each request is self-contained; optional session state is lightweight.
- Structured responses: responses are validated via Pydantic models.
- Logging and observability: JSON logs with consistent fields for production pipelines.

## API Flow Overview

User Query
-> Input sanitization and validation
-> Vagueness detection (Ollama, with fallback in service)
-> Clarification response if vague
-> Category and product reasoning pipeline
-> Provider fallback: Gemini -> GROQ -> OpenAI -> Ollama
-> Product listing enrichment via SerpAPI
-> Structured response assembly (`QueryResponse`)

## Main Endpoint

- `POST /v1/query`
- Request model: `app/models/requests.py::QueryRequest`
- Response model: `app/models/responses.py::QueryResponse`

## Error Handling

- Validation failures return `422` with specific details.
- AI orchestration failures return `503` through `AIServiceException`.
- Unhandled exceptions are converted to `500` with safe generic messages.

## Notes for Integrators

- For vague queries, the response status is `clarification_needed`.
- For clear queries, the response status is `recommendations` and includes categories.
- Provider credentials are managed in `.env` and loaded by `app/core/config.py`.
