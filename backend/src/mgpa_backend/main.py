"""FastAPI application entry point."""

from typing import Annotated

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from mgpa_backend.db import get_db

app = FastAPI(title="MGPA API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check: answers as long as the server process is running."""
    return {"status": "ok"}


@app.get("/health/db")
def health_db(db: Annotated[Session, Depends(get_db)]) -> dict[str, str]:
    """Readiness check: also verifies that the database answers a trivial query."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}
