"""FastAPI application entry point."""

from fastapi import FastAPI

app = FastAPI(title="MGPA API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check: answers as long as the server process is running."""
    return {"status": "ok"}
