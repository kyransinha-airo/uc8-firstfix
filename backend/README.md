# Backend

FastAPI + LangGraph. Runs on port **8008**.

```bash
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                       # all values optional for the offline tests
uvicorn app.main:app --reload --port 8008  # or: python -m app
pytest && ruff check . && ruff format --check .  # DB tests need TEST_ADMIN_URL
python -m app.scripts.migrate              # needs DATABASE_URL
```

| Path | Purpose |
| --- | --- |
| `app/main.py` | FastAPI app, CORS, error envelope; routes under `/api` |
| `app/api/` | Route modules |
| `app/core/` | Settings, lazy LLM client, `AppError`, live/record/replay model calls |
| `app/graphs/` | LangGraph parent graph and the four agent subgraphs |
| `app/services/` | Deterministic services: plain functions, no LLM, no clock |
| `app/tools/` | Read, calculate and write tools the agents call |
| `app/schemas/` | Pydantic models |
| `app/db/` | Connection helper and SQL migrations |
| `app/scripts/` | Command-line helpers |
