# Development And Deployment Guide

## Local Development

## Install Dependencies

```bash
python -m pip install -r Requirements/requirements.txt
python -m pip install -r Requirements/requirements-dev.txt
```

## Run API

From workspace root:

```bash
python -m uvicorn app.main:app --app-dir c:/Users/ksvar/Desktop/Genesis/RM/RecommendMe-API --host 127.0.0.1 --port 8000 --reload
```

Alternative from backend directory:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Static Syntax Validation

```bash
python -m compileall app
```

## Tests

```bash
python -m pytest -q tests
```

Current workspace result: no tests discovered in `tests/`.

## Container Workflow

## Docker Build

```bash
docker build -f Docker/Dockerfile -t recommendme-api .
```

## Docker Run

```bash
docker run --env-file .env -p 8000:8000 recommendme-api
```

## Docker Compose (API + Redis)

```bash
docker compose -f Docker/docker-compose.yml up --build
```

## Railway Deployment Configuration

Deployment descriptors:
- `railway.toml`
- `start.sh`
- `Docker/Dockerfile`

Configured behavior:
- Build with Dockerfile at `Docker/Dockerfile`.
- Start command: `./start.sh`.
- Health check path: `/v1/health`.

## CI/CD Workflow State

Files:
- `.github/workflows/ci.yml`
- `.github/workflows/deploy.yml`

Current state:
- Both workflows are present but guarded with `if: false` at job level.

Implication:
- CI lint/tests and deployment automation are currently disabled in repository workflow execution.

## Operational Recommendations

1. Set all required provider keys before running recommendation paths.
2. Override `AUTH_TOKEN_SECRET` in all non-local environments.
3. Treat CSV/JSON persistence as non-scaled mode.
4. Introduce Redis-backed session/cache for multi-instance deployments.
5. Enable CI pipelines before production promotion.
