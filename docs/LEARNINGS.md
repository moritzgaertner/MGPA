# Learnings

One entry per milestone: what I built, what I learned, and how I would explain it in an interview.

## M0 — Setup

**Built:** monorepo skeleton, Postgres 18 + pgvector via Docker Compose, backend Python project
with uv (ruff, mypy, pytest), GitHub Actions CI, architecture diagram.

**Learned**
- *Frontend / API / backend / database* — the browser UI talks to the backend over HTTP requests;
  the backend does the work and persists data in the database.
- *Docker Compose* — describes infrastructure as a file, so the same database starts identically
  on my laptop, in CI and on the server. Data lives in a named volume, outside the container.
- *Bind ports to `127.0.0.1`* — otherwise the database is reachable from the network.
- *Secrets* — only `.env.example` is committed; `.env` is gitignored.
- *uv + `uv.lock`* — the lock file pins every package version, making installs reproducible.
- *`src` layout* — tests import the installed package, not files that happen to be lying around.
- *CI* — every push runs lint, format check, type check and tests on a fresh machine.
  Pin actions to tags that exist: `setup-uv` only publishes exact versions (`v10.3.0`, not `v10`).

**Comprehension questions**
1. *Why `127.0.0.1:5432` instead of `5432`?* — Binds the port to localhost only. Without it, a VPS
   exposes the database to the internet, where bots scan for open ports and brute-force passwords.
   Docker can bypass `ufw`, so the bind address is the reliable protection.
2. *Committed `pyproject.toml` but not `uv.lock`?* — `uv sync --locked` in CI fails because the lock
   file no longer matches. Good: it prevents different machines from silently installing different
   versions ("works on my machine").
3. *Upload a PDF, then ask about it?* — Upload: frontend → API stores file + `pending` row → Dagster
   sensor → parse, chunk, embed → chunks in pgvector. Question: frontend → API → agent → Claude calls
   `search_knowledge` → question embedded → nearest-neighbour search → Claude answers with sources,
   streamed via SSE, traced in Langfuse. Both flows are decoupled, so the UI shows document status.

**Interview: "Why Postgres + pgvector instead of a dedicated vector database?"**
For a single-user app the data volume is small, and keeping vectors next to the relational data
means one system to run, back up and query — I can join chunks with their source documents in
plain SQL. A dedicated vector DB only pays off at scales or query patterns we do not have.
