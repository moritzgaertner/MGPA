# mgpa-backend

FastAPI backend and Pydantic AI agent.

```bash
uv sync                    # install dependencies
uv run ruff check .        # lint
uv run ruff format --check .
uv run mypy src tests      # type check
uv run pytest              # tests (needs the Postgres container running)

uv run fastapi dev src/mgpa_backend/main.py   # dev server on http://localhost:8000/docs

uv run alembic upgrade head                    # apply all migrations
uv run alembic revision --autogenerate -m "…"  # create a migration from model changes
uv run alembic check                           # fail if models and migrations differ
```
