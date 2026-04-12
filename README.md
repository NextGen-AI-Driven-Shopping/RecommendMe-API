# RecommendMe API

FastAPI backend for conversational recommendations.

## Canonical Documentation

- Backend reference (source of truth): `docs/BackendCodebaseReference.md`
- Documentation audit report: `docs/DocumentationValidationReport.md`

## Quick Start

Install dependencies:

```bash
python -m pip install -r Requirements/requirements.txt
python -m pip install -r Requirements/requirements-dev.txt
```

Run locally:

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Syntax check:

```bash
python -m compileall app
```

Tests:

```bash
python -m pytest -q tests
```

Current repository state: `tests/` contains no test files in this workspace.

## API Surface Summary

System:
- `GET /`
- `GET /health`
- `GET /v1/health`

Recommendation:
- `POST /v1/query`
- `POST /v1/query/sufficiency_check`
- `GET /v1/sessions/{session_id}`
- `GET /v1/sessions/{session_id}/exists`
- `POST /v1/chat/mode`

Auth:
- `POST /v1/auth/signup`
- `POST /v1/auth/login`
- `POST /v1/auth/forgot-password`
- `POST /v1/auth/reset-password`
- `GET /v1/auth/me` (bearer)

Profile:
- `GET /v1/profile` (bearer)
- `POST /v1/profile` (bearer)
- `PUT /v1/profile/update` (bearer)
- `GET /v1/profile/avatars`
- `POST /v1/profile/avatar/upload` (bearer)

## Storage Model

- Users: CSV file (`USERS_CSV_PATH`, default `app/data/users.csv`)
- Profiles: JSON file (`PROFILE_STORE_PATH`, default `app/data/profiles.json`)
- Sessions: in-memory process store (`app/utils/session.py`)

## Deployment Files

- Railway config: `railway.toml`
- Startup script: `start.sh`
- Container files: `Docker/Dockerfile`, `Docker/docker-compose.yml`
- CI/CD workflows: `.github/workflows/ci.yml`, `.github/workflows/deploy.yml`

Current workflow state: both GitHub Actions jobs are present but disabled via `if: false`.
