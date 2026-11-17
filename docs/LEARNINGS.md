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

**Interview (M2): "How does the frontend stay in sync with the backend?"**
The backend's FastAPI generates an OpenAPI schema, from which I generate the TypeScript types, and CI
fails if the committed schema differs from the backend — so a renamed field breaks the build, not
production. At runtime TanStack Query caches server data per query key, and every mutation
invalidates the affected keys, so lists refresh themselves after a change.

## M3 — Observability

**Built:** every agent run (chat and summary) is traced to Langfuse Cloud (EU) via OpenTelemetry:
full prompt incl. pinned notes, answer, tokens, cost, latency. Traces are named (chat/summary),
grouped into a session per conversation, labelled with an environment. Tracing is off without keys,
so CI and tests never send data. Tests also got their own database (`mgpa_test`).

**Learned**
- *OpenTelemetry* — vendor-neutral standard for traces/spans; Pydantic AI emits spans,
  Langfuse is just the backend that stores and prices them (swappable).
- *Instrumentation can overlap* — the Anthropic SDK emitted its own spans too, so every call was
  counted twice in Langfuse. Found only in the live check; fixed with `open_telemetry=False` on the
  SDK client and pinned with a regression test. Always verify cost numbers against a manual calc
  (886 in × $0.10/M + 33 out × $0.50/M = $0.000105 ✓).
- *Test isolation* — tests that share the dev database silently depend on real data. A separate
  test database (created + migrated in `conftest.py`) removes that coupling.
- *Privacy* — traces contain full prompts (incl. personal notes) and live at a third party;
  EU region, Hobby plan = 30 days visible. Masking is possible but kills debugging value.
- *Vendor APIs change* — Langfuse's v1 trace-read endpoint now returns 410; reads go through
  `/api/public/v2/observations`, which is rate-limited (poll sparingly).

**Interview: "How do you know what your agent costs and why it answered something?"**
Every agent run is traced with OpenTelemetry into Langfuse, so for each answer I see the exact
prompt — system prompt, pinned notes, history — plus tokens, cost and latency, grouped per
conversation. That's how I found that every call was being counted twice: two layers were both
instrumenting the model call, and I disabled the redundant one and locked that in with a test.

## M4 — Knowledge base (RAG)

**Built:** upload of Markdown/text files or pasted text (no PDF — deliberate scope cut), a Dagster
pipeline (sensor → one dynamic partition per document → asset that chunks, embeds with Voyage
`voyage-4` and stores in pgvector with an HNSW index), an agent tool `search_knowledge` with source
citations, and a `/knowledge` page with live status. Chat streaming moved to `run_stream_events`.

**Learned**
- *RAG* — answer from retrieved passages instead of model memory: chunk → embed → nearest
  neighbours by cosine similarity → passages + sources into the prompt → cited answer.
- *Chunking* — Markdown headings give each chunk a "where am I" path (`plan.md › Day B`), used both
  for the embedding input and for citations.
- *Embedding choice is sticky* — the vector size is in the schema; switching models means
  re-embedding everything. Documents vs. queries are embedded with different `input_type`.
- *Orchestration* — Dagster sensor + run keys (`id@updated_at`) make ingestion idempotent; a
  re-process bumps `updated_at` and so starts a new run.
- *Tool calls and streaming* — `run_stream` ends at the first text, so "Let me check…" + tool call
  would silently skip the tool; `run_stream_events` streams text and tool events across the run.
- *Failure states must be visible* — a live run showed a setup error left documents `pending`
  forever; every failure path now sets `failed` + reason (regression test).
- *Security* — files are stored under their SHA-256, never the client-supplied name.

**Interview: "How does your RAG pipeline work, and why Dagster?"**
Uploads only store the file and a `pending` row; a Dagster sensor turns each pending document into a
partition of an asset that chunks it along Markdown headings, embeds the chunks with Voyage and
writes them to pgvector. The chat agent has a `search_knowledge` tool that embeds the question, does
a cosine nearest-neighbour search and returns passages with their source, which Claude cites. Dagster
gives me per-document lineage, run history and re-materialisation, which a cron script wouldn't.

## M5 — Tools with human-in-the-loop

**Built:** write tools only *propose* (`actions` table: kind, JSON payload, label, status
proposed → confirmed / rejected); the chat streams a `proposal` event and renders a card with
Save / Discard; confirm executes deterministically in the backend (`actions.REGISTRY`), without
another LLM call. Tools: `propose_note`, `find_notes` (read-only, no confirmation).

**Learned**
- *Two HITL designs* — (a) pause the agent run on a tool and resume it after approval (needs the
  full run state persisted, and one more LLM call per decision); (b) proposal tools + direct
  execution on confirm. Chose (b): simpler, cheaper, several proposals per answer.
- *Validate twice* — tool arguments are validated when proposing (invalid → `ModelRetry`, the model
  fixes them) and again on confirm, so a stored payload can't bypass the rules.
- *Idempotency* — confirming twice returns 409; an action can only leave `proposed` once.
- *Extensible by registry* — new action kinds (training, meals, weight) = payload model + executor;
  `kind` is a string column, so no DB migration per new kind.

**Interview: "How do you keep an agent from writing wrong data?"**
The agent has no direct write access: its write tools only create proposals, which the user sees as
cards and confirms or discards. On confirm, the backend re-validates the payload and executes it in a
single transaction — deterministic code, no second model call — and an action can be confirmed only
once.

## Training — first domain module

**Built:** tables `exercises` (plan order, named machine settings, aliases, active flag),
`training_sessions`, `training_entries` (weight × sets); one-off importer for the old Excel +
CONTEXT.md; agent tools `training_briefing`, `exercise_history`, `propose_training_log`,
`propose_machine_settings`; `/training` page with plan, sessions and progress charts.

**Learned**
- *Domain module blueprint* — models + service (pure logic) + tool builders (validate model input
  into proposals) + router (UI) + page. Weight/habits and later applications follow the same shape.
- *Let code resolve, not the LLM* — abbreviations ("BP") are matched in Python (normalize + aliases,
  difflib suggestions on a miss → `ModelRetry`), so the model can't invent exercises.
- *JSON vs JSONB* — JSONB re-sorts object keys; machine settings must keep "Sitz, Knie, Fuß" order,
  so `settings` and the action payload use plain JSON.
- *Data migrations* — changing a column's shape needs a migration that converts existing rows, not
  just the schema change Alembic autogenerates.
- *Personal data stays out of git* — the importer reads the owner's files at run time.

**Interview: "How did you integrate an existing workflow into the agent?"**
I modelled the domain in Postgres, imported the old Excel once, and exposed it to Claude as a few
narrow tools: read tools return compact text, write tools only create proposals. Fuzzy matching of
abbreviations happens in deterministic code, and on a miss the tool returns suggestions so the model
retries instead of guessing.

## Login — single-user auth

**Built:** username + argon2 password hash in `.env` (set by a CLI, never typed into chat), signed
session cookie (HttpOnly, SameSite=Lax, Secure outside dev, 30 days), all routers except `/auth` and
`/health` behind `require_user`, login lockout after 5 failures / 15 min per IP, frontend guard that
redirects to `/login?redirect=…`.

**Learned**
- *Sessions vs JWT* — one user, one browser: a server-signed cookie is simpler and can't be read by
  JavaScript (XSS); JWTs mostly pay off with many services or third-party clients.
- *Constant-time checks* — compare usernames with `secrets.compare_digest` and verify a dummy hash
  for unknown users, so response time doesn't reveal which part was wrong.
- *SameSite=Lax* blocks cross-site POSTs carrying the cookie (CSRF) without extra tokens.
- *Behind a proxy* the client IP is Caddy's unless uvicorn trusts `X-Forwarded-For` — matters for
  the lockout.
- *Open redirects* — `?redirect=` only accepts same-site paths.

**Interview: "How did you secure a single-user app on the internet?"**
HTTPS via Caddy, a password stored only as an argon2 hash in the server's environment, and a signed
HttpOnly session cookie with SameSite=Lax; every API route depends on a `require_user` check except
login and health. Repeated failures lock the IP out for 15 minutes, which makes online guessing
impractical.

## Body weight & habits

**Built:** `body_weights` (one row per day, re-entry replaces), `habits` (weekly goal, source
`manual` or `training`), `habit_checks` (row = ticked); chat tools `propose_weight`,
`propose_habit_checkin`, `tracking_overview`; `/tracking` page with a week grid (optimistic ticks),
weigh-in field, 7-day trend, chart and weekly averages (SQL `date_trunc('week')`); habits.json
importer.

**Learned**
- *Derived instead of duplicated* — "Gym" is not ticked; it is computed from training sessions, so
  the two can never disagree.
- *Presence as data* — a habit check is just a row; unticking deletes it. A unique constraint
  `(habit_id, date)` makes ticking idempotent.
- *Concurrency bug found live* — Claude called two write tools in one response; Pydantic AI runs them
  in parallel, and both used one SQLAlchemy session from two threads ("This transaction is closed").
  Fix: a per-turn `asyncio.Lock` around all DB work of the tools; a regression test with a fake
  model making two parallel tool calls reproduces it.
- *Optimistic UI* — the checkbox flips before the server answers and rolls back on error; feels
  instant on a phone.
- *React detail* — `mutate(…, { onSuccess })` callbacks don't fire if the component unmounts first
  (here: a `key` that changed with the fetched data). Put lasting side effects in the hook.

**Interview: "Tell me about a bug you found in production-like testing."**
In an end-to-end test, "weight 82.4 and habits reading, vitamins" failed: Claude issued two tool
calls at once, the framework executed them concurrently, and both used the same database session
from different threads. I reproduced it with a fake model in a test, then serialized database access
per chat turn with an asyncio lock — the test fails without the fix and passes with it.
