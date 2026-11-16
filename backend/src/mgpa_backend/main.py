"""FastAPI application entry point."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from mgpa_backend.config import get_settings
from mgpa_backend.db import DbSession
from mgpa_backend.observability import setup_tracing, shutdown_tracing
from mgpa_backend.routers import chat, conversations, notes

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Runs once at server start (before `yield`) and once at shutdown (after)."""
    setup_tracing(get_settings())
    yield
    shutdown_tracing()


app = FastAPI(title="MGPA API", version="0.1.0", lifespan=lifespan)
app.include_router(conversations.router)
app.include_router(chat.router)
app.include_router(notes.router)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check: answers as long as the server process is running."""
    return {"status": "ok"}


@app.get("/health/db")
def health_db(db: DbSession) -> dict[str, str]:
    """Readiness check: also verifies that the database answers a trivial query."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}
