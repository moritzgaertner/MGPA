# Dagster daemon: runs the sensor that ingests new knowledge-base documents.
# No web UI in production (saves RAM); use `dagster dev` locally to inspect runs.
# Build context: repository root (the pipelines depend on the backend package).
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

COPY backend/ /app/backend/
WORKDIR /app/pipelines
COPY pipelines/pyproject.toml pipelines/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY pipelines/ ./
RUN uv sync --locked --no-dev

ENV PATH="/app/pipelines/.venv/bin:$PATH" \
    DOCUMENTS_DIR=/data/documents \
    DAGSTER_HOME=/dagster_home
RUN useradd --system --create-home --uid 10001 mgpa \
    && mkdir -p /data/documents /dagster_home \
    && printf 'telemetry:\n  enabled: false\n' > /dagster_home/dagster.yaml \
    && chown -R mgpa /data /dagster_home
USER mgpa

CMD ["dagster-daemon", "run", "-m", "mgpa_pipelines.definitions"]
