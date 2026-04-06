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
	- `query.py` - conversational orchestration
	- `sessions.py` - session snapshot hydration endpoints
	- `auth.py` - signup/login/password reset/me
	- `profile.py` - profile CRUD and avatar upload
- `models/` - Pydantic schemas
- `services/` - orchestration/business logic
	- `auth_csv.py` - CSV credential storage
	- `profile_store.py` - JSON profile storage
	- `auth_token.py` - token create/verify
- `providers/` - external LLM adapters
- `prompts/` - prompt templates
- `core/` - middleware, logging, exception handling, security
- `utils/` - helper utilities
- `data/users.csv` - MVP auth storage
- `data/profiles.json` - profile persistence

## Testing

- `tests/unit` - focused logic tests
- `tests/integration` - endpoint flow tests
