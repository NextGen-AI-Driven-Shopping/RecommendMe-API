# Project Structure

```text
RecommendMe-API/
|-- app/
|   |-- api/
|   |   |-- v1/
|   |   |   |-- health.py
|   |   |   `-- query.py
|   |   |-- deps.py
|   |   `-- README.md
|   |-- core/
|   |   |-- config.py
|   |   |-- exceptions.py
|   |   |-- logger.py
|   |   |-- middleware.py
|   |   `-- security.py
|   |-- models/
|   |   |-- internal.py
|   |   |-- requests.py
|   |   `-- responses.py
|   |-- prompts/
|   |   |-- category_reasoning.py
|   |   |-- intent_extraction.py
|   |   |-- product_ranking.py
|   |   `-- vagueness_check.py
|   |-- providers/
|   |   |-- __init__.py
|   |   |-- base.py
|   |   |-- gemini_provider.py
|   |   |-- groq_provider.py
|   |   |-- openai_provider.py
|   |   `-- ollama_provider.py
|   |-- services/
|   |   |-- cache.py
|   |   |-- products.py
|   |   |-- ranking.py
|   |   |-- recommender.py
|   |   `-- vagueness.py
|   |-- utils/
|   |   |-- formatters.py
|   |   |-- session.py
|   |   `-- validators.py
|   `-- main.py
|-- docs/
|   |-- api_architecture.md
|   |-- ai_model_pipeline.md
|   `-- project_structure.md
|-- scripts/
|-- tests/
|-- Dockerfile
|-- docker-compose.yml
|-- main.py
|-- requirements.txt
`-- README.md
```

## Notes

- `app/providers/` is the abstraction layer for model providers.
- `app/services/recommender.py` enforces fallback order for category reasoning.
- `app/api/v1/query.py` is the API orchestration entrypoint.
