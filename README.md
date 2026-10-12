# MGPA — personal AI assistant

A single-user AI assistant: streamed chat with Claude, RAG over my own documents,
note/task tools with human-in-the-loop confirmation, and long-running jobs orchestrated by Temporal.

> Work in progress. Architecture, setup and screenshots follow in later milestones.

## Repo layout

| Path | Contents |
|---|---|
| `frontend/` | React + Vite + Chakra UI v3 + TanStack Router/Query |
| `backend/` | FastAPI, Pydantic AI agent, SQLAlchemy + Alembic |
| `workflows/` | Temporal worker (research workflow, daily briefing) |
| `pipelines/` | Dagster document ingestion (parse, chunk, embed → pgvector) |
| `infra/` | Docker Compose, Caddy |
| `docs/` | Architecture and learnings |
