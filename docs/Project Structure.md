# Backend Project Structure

```text
RecommendMe-API/
|-- app/
|   |-- config/
|   |-- core/
|   |-- data/
|   |   |-- users.csv
|   |   `-- profiles.json
|   |-- models/
|   |-- prompts/
|   |-- providers/
|   |-- routes/
|   |   `-- v1/
|   |-- services/
|   |-- utils/
|   `-- main.py
|-- docs/
|-- Docker/
|-- Environment/
|-- Requirements/
|-- tests/
|   |-- integration/
|   `-- unit/
|-- main.py
|-- pytest.ini
|-- railway.toml
`-- README.md
```

## Notes

- `routes/v1/query.py` is the orchestration entrypoint.
- `routes/v1/sessions.py` exposes hydratable session snapshots for frontend polling.
- `routes/v1/auth.py` and `routes/v1/profile.py` handle auth/profile APIs.
- `services/` contains domain logic (auth, vagueness, recommendation, products, profile persistence).
- `providers/` encapsulates LLM-specific API calls and fallback compatibility.
