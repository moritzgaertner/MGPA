# mgpa-pipelines

Dagster code location: ingests knowledge-base documents (chunk + embed into pgvector).

\ash
uv sync
mkdir -p .dagster_home && DAGSTER_HOME=\Microsoft.PowerShell.Core\FileSystem::\wsl.localhostuntu-24.04\home\morit\code\MGPA/.dagster_home uv run dagster dev   # UI on http://localhost:3000
uv run ruff check . && uv run mypy src tests && uv run pytest
\n