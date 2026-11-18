# FastAPI backend. Build context: repository root.
#   docker build -f infra/backend.Dockerfile .
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

WORKDIR /app/backend

# Dependencies first (cached as long as the lock file doesn't change), then the code.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY backend/ ./
RUN uv sync --locked --no-dev

ENV PATH="/app/backend/.venv/bin:$PATH" \
    DOCUMENTS_DIR=/data/documents
RUN useradd --system --uid 10001 mgpa && mkdir -p /data/documents && chown -R mgpa /data
USER mgpa

EXPOSE 8000
# Bring the schema up to date, then serve. --proxy-headers: trust X-Forwarded-For from the
# web container (the backend is only reachable inside the Docker network), so the login
# lockout sees the real client IP instead of the proxy's.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn mgpa_backend.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
