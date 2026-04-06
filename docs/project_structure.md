# Project Structure (Backend)

## Top-Level

- `app/` - source code
- `tests/` - unit + integration tests
- `Requirements/` - dependency files
- `docs/` - architecture and flow docs
- `Docker/` - container assets

## `app/` Details

- `main.py` - FastAPI app configuration
- `routes/v1/` - HTTP endpoints
- `models/` - Pydantic schemas
- `services/` - orchestration/business logic
- `providers/` - external LLM adapters
- `prompts/` - prompt templates
- `core/` - middleware, logging, exception handling, security
- `utils/` - helper utilities
- `data/users.csv` - MVP auth storage

## Testing

- `tests/unit` - focused logic tests
- `tests/integration` - endpoint flow tests
