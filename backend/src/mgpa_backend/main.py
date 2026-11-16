"""FastAPI application entry point."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy import text
from starlette.middleware.sessions import SessionMiddleware

from mgpa_backend.auth import require_user
from mgpa_backend.config import get_settings
from mgpa_backend.db import DbSession
from mgpa_backend.observability import setup_tracing, shutdown_tracing
from mgpa_backend.routers import actions, auth, chat, conversations, documents, notes, training

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Runs once at server start (before `yield`) and once at shutdown (after)."""
    setup_tracing(get_settings())
    yield
    shutdown_tracing()


settings = get_settings()
app = FastAPI(title="MGPA API", version="0.1.0", lifespan=lifespan)

# Signed session cookie: HttpOnly (JavaScript can't read it), SameSite=Lax (other sites can't
# send it with POST requests, which blocks CSRF), Secure (HTTPS only) outside development.
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret.get_secret_value(),
    session_cookie="mgpa_session",
    max_age=settings.session_max_age_days * 24 * 3600,
    same_site="lax",
    https_only=settings.app_env != "development",
)

# Everything except /auth and /health requires a logged-in session.
protected = [Depends(require_user)]
app.include_router(auth.router)
app.include_router(conversations.router, dependencies=protected)
app.include_router(chat.router, dependencies=protected)
app.include_router(notes.router, dependencies=protected)
app.include_router(documents.router, dependencies=protected)
app.include_router(actions.router, dependencies=protected)
app.include_router(training.router, dependencies=protected)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check: answers as long as the server process is running."""
    return {"status": "ok"}


@app.get("/health/db")
def health_db(db: DbSession) -> dict[str, str]:
    """Readiness check: also verifies that the database answers a trivial query."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}
