# Backend Project Structure

```text
RecommendMe-API/
|-- app/
|   |-- config/
|   |-- core/
|   |-- data/
|   |   `-- users.csv
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
- `services/` contains domain logic (auth, vagueness, recommendation, products).
- `providers/` encapsulates LLM-specific API calls.
