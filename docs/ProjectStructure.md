# Superseded Document

This file is retained for historical context. For current implementation-accurate backend documentation, use:
- backend_overview.md
- architecture.md
- api_reference.md
- data_flow.md
- ai_integration.md

---

# Project Structure

## Scope

This document covers the backend repository structure under `RecommendMe-API`.

For each directory and file, it documents:
- Purpose (what it does)
- Necessity (why it exists)

## Clean Tree

```text
RecommendMe-API/
|- .github/workflows/
|- app/
|  |- config/
|  |- core/
|  |  |- cache_cleaner/
|  |  `- logs/
|  |- data/
|  |- models/
|  |- prompts/
|  |- providers/
|  |- routes/
|  |  `- v1/
|  |- services/
|  `- utils/
|- Docker/
|- docs/
|- Environment/
|- Requirements/
|- tests/
|- .env
|- .env.example
|- .gitignore
|- main.py
|- pytest.ini
|- railway.toml
|- README.md
`- start.sh
```

## Directory Catalog

| Path | Purpose | Necessity |
|---|---|---|
| `.github/workflows/` | CI and deployment workflow definitions | Enables automated quality gates and deployment automation when activated |
| `app/` | Backend source code | Core runtime implementation |
| `app/config/` | Typed settings and provider-model catalog | Centralized runtime configuration |
| `app/core/` | Security, middleware, logging, exceptions, startup helpers | Cross-cutting runtime concerns |
| `app/core/cache_cleaner/` | Cache artifact cleanup logic | Startup hygiene to remove stale cache artifacts |
| `app/core/logs/` | Runtime log output location | Structured log persistence target |
| `app/data/` | File-backed runtime persistence (CSV/JSON/uploads) | MVP persistence without external DB |
| `app/models/` | Pydantic request/response/internal schemas | Enforces contract consistency |
| `app/prompts/` | LLM prompt templates | Centralized prompt engineering |
| `app/providers/` | AI provider adapters | Provider abstraction and fallback support |
| `app/routes/` | Route package root | API endpoint organization |
| `app/routes/v1/` | Versioned API handlers | Stable versioned public API boundary |
| `app/services/` | Business logic modules | Feature orchestration and domain behavior |
| `app/utils/` | Utility helpers | Shared helper functions and session state tooling |
| `Docker/` | Container build and local compose files | Standardized local/prod container workflows |
| `docs/` | Backend technical documentation | Developer onboarding and maintenance reference |
| `Environment/` | Alternate env templates | Environment setup support |
| `Requirements/` | Dependency manifests | Reproducible package installation |
| `tests/` | Test suite location | Test discovery target configured by pytest |

## Top-Level File Catalog

| File | Purpose | Necessity |
|---|---|---|
| `.env` | Local runtime environment values | Runtime secrets and variable overrides (not for source control) |
| `.env.example` | Public env template | Documents expected environment keys |
| `.gitignore` | Ignore rules | Prevents committing secrets/build artifacts |
| `main.py` | Root launcher script | Convenience app startup entry |
| `pytest.ini` | Pytest config | Standardized test discovery |
| `railway.toml` | Railway deployment config | Build/start/healthcheck contract for Railway |
| `README.md` | Repository quick-start overview | Human entrypoint for repository consumers |
| `start.sh` | Runtime startup shell script | Container/platform startup contract |

## App File Catalog

## `app/`

| File | Purpose | Necessity |
|---|---|---|
| `app/__init__.py` | Package marker | Python package import support |
| `app/main.py` | FastAPI app factory and initialization | Central runtime assembly |

## `app/config/`

| File | Purpose | Necessity |
|---|---|---|
| `app/config/__init__.py` | Config package export | Cleaner imports for settings |
| `app/config/settings.py` | Typed settings loader and validators | Runtime configuration control |
| `app/config/provider_models.yml` | Provider model list definitions | Decouples model lists from code defaults |

## `app/core/`

| File | Purpose | Necessity |
|---|---|---|
| `app/core/__init__.py` | Core package marker | Import organization |
| `app/core/auth.py` | Bearer token auth dependency | Protected endpoint user resolution |
| `app/core/exceptions.py` | Custom exceptions and handlers | Consistent error response strategy |
| `app/core/logger.py` | JSON logger configuration | Structured observability |
| `app/core/middleware.py` | Request logging/correlation middleware | Request-level tracing and timing |
| `app/core/security.py` | CORS configuration | Controlled cross-origin access |
| `app/core/cache_cleaner/__init__.py` | cache cleaner export | Startup cache-clean utility wiring |
| `app/core/cache_cleaner/cleaner.py` | cache artifact cleanup logic | Remove stale cache files/dirs at startup |
| `app/core/logs/app.log` | runtime log file | Persisted runtime logs |

## `app/data/`

| File | Purpose | Necessity |
|---|---|---|
| `app/data/users.csv` | User auth store | File-backed user persistence |
| `app/data/profiles.json` | User profile store | File-backed profile persistence |

## `app/models/`

| File | Purpose | Necessity |
|---|---|---|
| `app/models/__init__.py` | models package marker | Import organization |
| `app/models/requests.py` | request payload models | Endpoint input contract validation |
| `app/models/responses.py` | response payload models | Endpoint output contract consistency |
| `app/models/internal.py` | internal pipeline models | Non-API service-level data transport |

## `app/prompts/`

| File | Purpose | Necessity |
|---|---|---|
| `app/prompts/__init__.py` | prompts package marker | Import organization |
| `app/prompts/category_reasoning.py` | category reasoning prompt/messages | AI recommendation structure generation |
| `app/prompts/vagueness_check.py` | vagueness prompt/messages | AI query sufficiency classification |

## `app/providers/`

| File | Purpose | Necessity |
|---|---|---|
| `app/providers/__init__.py` | provider package export | Aggregated provider imports |
| `app/providers/base.py` | provider interfaces and normalized models | Provider abstraction boundary |
| `app/providers/groq_provider.py` | Groq adapter | Primary provider integration |
| `app/providers/openai_provider.py` | OpenAI adapter | fallback/provider support |
| `app/providers/gemini_provider.py` | Gemini adapter | fallback/provider support |
| `app/providers/ollama_provider.py` | Ollama adapter | local fallback support |

## `app/routes/`

| File | Purpose | Necessity |
|---|---|---|
| `app/routes/__init__.py` | route package marker | Import organization |

## `app/routes/v1/`

| File | Purpose | Necessity |
|---|---|---|
| `app/routes/v1/__init__.py` | v1 route package marker | Import organization |
| `app/routes/v1/router.py` | v1 route aggregator | Single mounted API router |
| `app/routes/v1/query.py` | query/sufficiency endpoints | main recommendation request path |
| `app/routes/v1/auth.py` | authentication endpoints | account and token lifecycle |
| `app/routes/v1/profile.py` | profile endpoints | profile read/update/avatar operations |
| `app/routes/v1/sessions.py` | session endpoints | session hydration and existence checks |
| `app/routes/v1/chat_mode.py` | chat follow-up endpoint | post-recommendation Q&A support |
| `app/routes/v1/health.py` | health endpoint | external/internal service probe status |

## `app/services/`

| File | Purpose | Necessity |
|---|---|---|
| `app/services/__init__.py` | service package marker | import organization |
| `app/services/auth_csv.py` | CSV auth persistence logic | file-backed auth implementation |
| `app/services/auth_token.py` | token create/verify | bearer auth mechanism |
| `app/services/cache.py` | in-memory cache helpers | short-term caching utilities |
| `app/services/chat_mode.py` | chat follow-up answering logic | contextual post-recommendation dialogue |
| `app/services/clarification.py` | clarification planning and scoring | structured question strategy |
| `app/services/dynamic_intent_analyzer.py` | dynamic signal extraction | domain-aware follow-up generation |
| `app/services/products.py` | product fetching + fallback | external product retrieval pipeline |
| `app/services/profile_store.py` | JSON profile persistence | profile CRUD storage layer |
| `app/services/ranking.py` | ranking pipeline module | legacy/additional ranking path |
| `app/services/recommender.py` | provider fallback recommendation planner | category/product recommendation orchestration |
| `app/services/suggestions.py` | suggestion response wrappers | legacy/additional response composition path |
| `app/services/vagueness.py` | vagueness classification service | clarification-vs-recommendation branching |

## `app/utils/`

| File | Purpose | Necessity |
|---|---|---|
| `app/utils/__init__.py` | utility package marker | import organization |
| `app/utils/formatters.py` | response formatting helpers | consistent query response shaping |
| `app/utils/prompt_utils.py` | prompt helper functions | shared prompt/message assembly logic |
| `app/utils/session.py` | in-memory session store helpers | session continuity primitives |
| `app/utils/validators.py` | query sanitization and safety checks | pre-processing guardrails |

## Supporting Infrastructure File Catalog

## `docs/`

| File | Purpose | Necessity |
|---|---|---|
| `docs/DocsIndex.md` | documentation navigation map | makes onboarding sequence explicit |
| `docs/SystemOverview.md` | backend scope and runtime overview | quick conceptual orientation |
| `docs/ArchitectureExplanation.md` | layered architecture and boundaries | explains module interaction model |
| `docs/ApiArchitecture.md` | API-specific architectural view | route/service/provider boundary clarity |
| `docs/ApiFlow.md` | endpoint inventory and execution flows | request-path operational understanding |
| `docs/AiModelPipeline.md` | AI stage and fallback pipeline | model orchestration transparency |
| `docs/LogicalFlow.md` | step-by-step backend runtime flow | concise behavior reference |
| `docs/ErrorHandlingStrategy.md` | exception and fallback strategy | reliability and troubleshooting guidance |
| `docs/ConfigurationAndEnvironmentSetup.md` | env/setup/config behavior | reproducible local/deploy configuration |
| `docs/ComponentResponsibilities.md` | major module deep responsibilities | maintenance and extension planning |
| `docs/ProjectStructure.md` | file and directory catalog | complete repository structure reference |
| `docs/DevelopmentAndDeploymentGuide.md` | local run, container, deployment guidance | operational execution playbook |
| `docs/BackendCodebaseReference.md` | consolidated technical reference | quick authoritative implementation snapshot |
| `docs/DocumentationValidationReport.md` | doc drift and compliance record | documentation governance and traceability |

## `Docker/`

| File | Purpose | Necessity |
|---|---|---|
| `Docker/Dockerfile` | container image build spec | reproducible deployment artifact |
| `Docker/docker-compose.yml` | local multi-service compose | easy local API + Redis setup |

## `Environment/`

| File | Purpose | Necessity |
|---|---|---|
| `Environment/.env.example` | env template | environment setup guidance |

## `Requirements/`

| File | Purpose | Necessity |
|---|---|---|
| `Requirements/requirements.txt` | runtime dependencies | production runtime package set |
| `Requirements/requirements-dev.txt` | dev/test dependencies | lint/test tooling package set |

## `.github/workflows/`

| File | Purpose | Necessity |
|---|---|---|
| `.github/workflows/ci.yml` | CI lint/test workflow definition | automated quality checks |
| `.github/workflows/deploy.yml` | deployment workflow definition | automated deployment path |

## Notes

- `tests/` exists but no test files were found in this workspace snapshot.
- Legacy modules (`app/services/ranking.py`, `app/services/suggestions.py`) exist but are not on the active `POST /v1/query` route path.

