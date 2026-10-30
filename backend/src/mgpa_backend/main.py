"""FastAPI application entry point."""

from fastapi import FastAPI
from sqlalchemy import text

from mgpa_backend.db import DbSession
from mgpa_backend.routers import chat, conversations

app = FastAPI(title="MGPA API", version="0.1.0")
app.include_router(conversations.router)
app.include_router(chat.router)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check: answers as long as the server process is running."""
    return {"status": "ok"}


@app.get("/health/db")
def health_db(db: DbSession) -> dict[str, str]:
    """Readiness check: also verifies that the database answers a trivial query."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}
