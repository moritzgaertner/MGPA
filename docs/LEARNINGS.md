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

## M1 — Backend

**Built:** FastAPI app with settings from env, SQLAlchemy models (conversations, messages, notes,
tasks, documents) with Alembic migrations, CRUD endpoints for conversations, and `POST /chat`
streaming Claude's answer via Server-Sent Events using a Pydantic AI agent. 26 tests, all against a
real Postgres; Claude is replaced by a fake model in tests.

**Learned**
- *ORM* — Python classes map to tables; `Mapped[str | None]` decides nullability.
- *Primary key / foreign key / relationship* — the FK is the real column and a rule the database
  enforces; `relationship()` is only a Python shortcut. `ON DELETE CASCADE` lets the database delete
  children; without it, deleting the parent is refused.
- *Migrations* — versioned schema changes. Autogenerate is a draft: read it (it stored enum names
  instead of values and missed `DROP TYPE` in downgrade), test up/down, and `alembic check` in CI.
- *`now()` is the transaction start time* — rows saved together share it, so order by `id`.
- *Schemas vs. models* — Pydantic schemas define the public API; models define storage. Internal
  columns never leak, and the database can change without breaking clients.
- *HTTP status codes* — 200/201/204 success, 404 not found, 422 invalid input (validated by
  Pydantic before my code runs). Bound every input (`limit ≤ 100`, title ≤ 200 chars).
- *Dependency injection* — endpoints receive a DB session via `Depends`; tests swap it for a
  rolled-back session, and swap Claude for a fake model.
- *async + SSE* — the server keeps serving while waiting for Claude; SSE streams text pieces over
  one open HTTP response. The status code is sent first, so anything that can 404 runs before the
  stream starts. Blocking DB calls inside async code go to a thread pool.
- *LLMs are stateless* — the full history is sent on every turn, so input tokens (cost) grow with
  conversation length. Model ID and effort come from env; default `claude-haiku-5-5` for cost.

**Comprehension questions** (asked during the milestone)
1. *Missing `ondelete="CASCADE"`?* — Postgres refuses to delete a conversation that has messages
   (foreign key violation).
2. *Why save the user message before calling Claude?* — If the model call fails or the user closes
   the tab, the question is not lost; it also guarantees it gets a smaller `id` than the answer.
3. *Why test with a fake model?* — No API cost, fast, deterministic output, no real key in CI.

**Interview: "How does your chat endpoint stream answers, and what happens if Claude fails?"**
The endpoint first saves the user message and loads the conversation history — as a dependency, so
a missing conversation is still a clean 404. Then it streams Claude's answer as Server-Sent Events
(`start`, `delta`…, `done`) and saves the full answer at the end; if the model call fails, the
client gets a generic `error` event while the details go to the server log.

## M1.5 — Context management

**Built:** notes with `is_pinned` (pinned notes go word for word into every turn's system prompt via
`@agent.instructions`), and a rolling conversation summary that folds older messages once a turn's
input exceeds a token threshold. Messages are never deleted; only what Claude receives shrinks.

**Learned**
- *Two kinds of context* — durable facts (pinned, never summarized) vs. conversation flow
  (summarizable). Summaries compress and lose numbers; explicit pinning beats guessing importance.
- *Rolling summary* — old summary + next chunk → new summary; keep the last N messages verbatim and
  start the kept part with a user message. Runs after `done`, failures are self-healing.
- *Adding a NOT NULL column to a filled table* needs a `server_default`.
- *SQLAlchemy identity map* — one session holds one object per row; collections loaded earlier are
  not refreshed automatically (only visible in tests that share a session).

## M2 — Frontend

**Built:** React + TypeScript SPA with Vite: Chakra UI v3 layout (sidebar, mobile drawer, dark mode),
TanStack Router file routes (`/chat`, `/chat/$conversationId`, `/notes`, `/knowledge`, `/tasks`),
TanStack Query for server state, types generated from the backend's OpenAPI schema, streaming chat
with Markdown, notes page with pin toggle. CI: ESLint, `tsc`, build, plus an API-contract check.

**Learned**
- *TypeScript* — JavaScript with types; `tsc` is the frontend's mypy. Vite strips the types at build.
- *React* — components (functions returning UI), props (inputs), state (`useState`): change state
  and React re-renders. Refs are not watched by React — never read them during render.
- *Routing* — file = page; URL params are parsed and validated once at the route (`notFound()`).
- *Server state* — TanStack Query caches by query key; mutations invalidate keys to refetch.
- *API contract* — FastAPI's OpenAPI → generated TS types; CI diffs the committed schema so backend
  and frontend can't drift apart. Dev proxy `/api` → backend avoids CORS.
- *Streaming in the browser* — `EventSource` is GET-only, so POST via `fetch` and parse SSE from the
  body stream, buffering incomplete blocks. Optimistic preview, then hand over to stored data.
- *Security* — `react-markdown` never renders raw HTML (no XSS from model output); dependency alerts
  (Dependabot) fixed with an npm `overrides` pin.
- *Tooling reality* — newest ≠ best: TS 7 not yet supported by typescript-eslint, so TS 6.

**Interview: "How does the frontend stay in sync with the backend?"**
The backend's FastAPI generates an OpenAPI schema, from which I generate the TypeScript types, and CI
fails if the committed schema differs from the backend — so a renamed field breaks the build, not
production. At runtime TanStack Query caches server data per query key, and every mutation
invalidates the affected keys, so lists refresh themselves after a change.
