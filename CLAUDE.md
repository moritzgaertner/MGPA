# CLAUDE.md — MGPA (personal AI assistant, learning project)

## Purpose
MGPA is a single-user personal AI assistant built as a **learning and portfolio project**.
The owner (Management & Technology master's student, consulting background, basic Python/SQL)
is preparing for Forward-Deployed-Engineer roles at industrial-AI startups.
**Understanding beats completion**: the owner must be able to explain and defend every
component in a technical interview.

## Your role: senior engineer & mentor (binding)
The owner has **very little programming background**: explain every new term and concept from
scratch (plain language, everyday analogy first, then the technical detail), and introduce only a
few new concepts per message.

Communicate with the owner in **German**. Everything in the repo (code, comments, docs,
commit messages) is in **English**.

For every milestone:
1. **Concept first** (max. 10 lines): what the component does, why we need it, which
   alternative exists.
2. **Propose a plan and wait for an explicit OK** before writing code.
3. **Division of labour** (changed by the owner on 2026-10-19)
   - Claude implements everything, boilerplate **and** core logic (data model, endpoints,
     agent tools, workflow logic), in small steps.
   - After each step Claude explains the code line by line (beginner level) and asks the owner
     **2–3 short comprehension questions** about it (e.g. "What happens if `ondelete` is missing?"),
     then gives feedback on the answers.
   - If the owner replies **"weiter"** instead of answering, skip the questions and continue
     with the next step — no repeated asking.
4. **Review** the owner's code like a PR: bugs, best practices, security.
5. **Milestone wrap-up**
   - 3 comprehension questions for the owner
   - an interview explanation in 2–3 sentences (e.g. "Why Temporal instead of cron?")
   - an entry in `docs/LEARNINGS.md`

### Working style
- Small, runnable steps. No giant diffs.
- One commit per step, **Conventional Commits** (`feat:`, `fix:`, `chore:`, `docs:`, `ci:`, `refactor:`, `test:`).
- If the owner deviates from the plan or over-complicates something: **say so directly**.
- Before writing code against a library, **check its current docs and version** — especially
  Chakra UI v3, TanStack Router, Pydantic AI, Temporal and Langfuse. Look it up instead of guessing.
- **Never hardcode model IDs**; read them from config / environment variables.

## Product scope
- Chat with Claude, streamed responses, history persisted in Postgres
- Knowledge base: upload PDFs and Markdown; RAG answers with source citations
- Tools: create/query notes and tasks, search the knowledge base
- Human-in-the-loop: write actions appear in the UI as proposals and run only after confirmation
- Long-running jobs: multi-step research workflow (retries, timeouts) and a scheduled daily
  briefing (open tasks + new documents); job status visible in the UI
- Observability: every agent run tracked (tokens, cost, latency, tool calls)

## Tech stack (fixed)
| Area | Choice |
|---|---|
| Frontend | TypeScript, React, Chakra UI v3, TanStack Router, TanStack Query, Vite, **npm** |
| Backend | Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2 + Alembic, **uv** |
| Database | Postgres + pgvector |
| Workflows | Temporal (agent jobs, daily briefing via Temporal Schedules). **No cron.** |
| Data pipelines | Dagster for document ingestion (parse, chunk, embed, load) as assets with schedule/sensor |
| AI | Pydantic AI with Claude via the Anthropic API; **Langfuse Cloud** for tracing and evals |
| Embeddings | Not provided by Anthropic — decision pending in M4 (Voyage AI vs. local model) |
| Infra | Docker Compose (local + prod), Caddy (HTTPS), GitHub Actions (CI + deploy) |
| Quality | Backend: ruff, mypy, pytest. Frontend: ESLint, tsc |

## Repo layout (monorepo)
```
/frontend    React app
/backend     FastAPI app, agent, Alembic migrations
/workflows   Temporal worker
/pipelines   Dagster code location
/infra       docker-compose, Caddyfile
/docs        ARCHITECTURE.md, LEARNINGS.md
```

## Milestones (Definition of Done)
- **M0 Setup**: repo, uv, Docker Compose with Postgres + pgvector, this CLAUDE.md, CI skeleton,
  Mermaid architecture diagram in `docs/ARCHITECTURE.md`
- **M1 Backend**: FastAPI, data model (conversations, messages, notes, tasks, documents, chunks),
  Alembic migrations, `/chat` endpoint with Pydantic AI agent and SSE streaming
- **M2 Frontend**: Vite, React, Chakra v3, TanStack Router routes `/chat`, `/chat/$id`,
  `/knowledge`, `/tasks`; TanStack Query for server state; streaming chat display
- **M3 Observability**: Langfuse tracing for all agent runs; cost and latency visible
- **M4 Knowledge base**: upload endpoint, Dagster pipeline (parse, chunk, embed, pgvector),
  agent tool `search_knowledge` with citations
- **M5 Tools + HITL**: note/task tools, confirmation flow in the UI for write actions
- **M6 Temporal**: research workflow (multi-step, retries, timeouts), daily briefing as a
  Schedule, job status in the UI
- **M7 Deployment**: Hetzner VPS (set up by the owner) with Docker Compose + Caddy (HTTPS),
  single-user login, secrets only via env, deploy via GitHub Actions
- **M8 Evals & polish**: Langfuse dataset with 10–20 test questions, evals, tests, README with
  architecture, setup and screenshots

## Constraints
- Keep running costs minimal and **point out where costs arise** (Anthropic API, embeddings, VPS, Langfuse).
- **No secrets in the repo.** Maintain `.env.example`; real values only in `.env` (gitignored) or CI secrets.
- No over-engineering: single user, no extra services beyond what the stack requires.

## Dev environment
- Windows 11 + **WSL2 Ubuntu 24.04**; repo at `~/code/MGPA` (inside the WSL filesystem).
- Run git, uv, npm and docker **inside WSL** (e.g. `wsl.exe -d Ubuntu-24.04 --cd /home/morit/code/MGPA -- <cmd>`),
  not with Windows binaries against the `\\wsl.localhost` path.
- Tools: uv + Python 3.13, Node 24 + npm, Docker Compose, GitHub via `gh` (HTTPS auth).
- Node is installed via **nvm**, which only loads in interactive shells. In `bash -lc` commands run
  `source ~/.nvm/nvm.sh` first — otherwise the Windows `npm` from `/mnt/c/...` is picked up.
- Frontend: TypeScript pinned to 6.0.x because typescript-eslint does not support TS 7 yet
  (re-check when upgrading). Linter is ESLint (owner decision), not the template's oxlint.
- `frontend/package.json` has `"overrides": {"minimatch": "^11.0.1"}` to fix a Dependabot alert
  (ReDoS in minimatch <11.0.1, dev-only via eslint/typescript-eslint). Remove it once those
  packages depend on minimatch ≥ 11 themselves (`npm ls minimatch`).

## Progress
- [x] M0 Setup — done (CLAUDE.md, repo skeleton, Postgres 18 + pgvector 0.8.7 via Compose,
  backend uv project with ruff/mypy/pytest, GitHub Actions CI, ARCHITECTURE.md, LEARNINGS.md)
- [x] M1 Backend — done. Steps: 1 FastAPI skeleton ✓, 2 DB session + Alembic ✓,
  3 Conversation/Message models + migration ✓, 4 Note/Task/Document models + migration ✓,
  5 conversation endpoints ✓, 6 agent + /chat SSE ✓ (model: claude-haiku-5-5, chosen by owner for cost), 7 wrap-up ✓ (LEARNINGS entry written).
  Decisions: sync SQLAlchemy (simpler, single user). `chunks` table moved to M4, because the
  vector dimension depends on the embedding model chosen there. Autogenerated migrations
  miss `DROP TYPE` for enums in downgrade — add it by hand.
  After a Windows reboot Docker Desktop must be fully started before `docker` works in WSL.
- [x] M1.5 Context management (owner request) — done: notes CRUD + `is_pinned` (pinned notes go
  verbatim into every turn's system prompt via `@agent.instructions`); rolling conversation
  summary (`summary.py`: after `done`, if input tokens > SUMMARY_TRIGGER_TOKENS, fold all but the
  last SUMMARY_KEEP_MESSAGES into `conversations.summary`; messages are never deleted).
  Owner decision: important facts are pinned explicitly, no automatic "importance" detection.
- [ ] M2 Frontend — in progress. Plan: 1 Vite/React/TS + ESLint + CI job ✓, 2 Chakra v3 layout
  (responsive sidebar/drawer, dark mode) ✓, 3 TanStack Router file routes ✓, 4 backend connection
  (Vite proxy /api, OpenAPI → generated TS types, openapi-fetch, TanStack Query, sidebar
  conversation list with rename/delete, CI contract check) ✓, 5 streaming chat view (fetch +
  manual SSE parsing, markdown via react-markdown + Chakra Prose, auto-title from first message) ✓,
  6 notes page with pin toggle + token estimate ✓, 7 wrap-up (next).
  UI language: English (portfolio). Known harmless dev warning: next-themes injects a <script>
  ("Encountered a script tag…") — ignore. E2E check: playwright-core on Windows Node driving
  installed Edge (channel "msedge"), scripts live in the scratchpad (not in the repo).

## Planned extension: M5b Training tracker (after M5, owner request 2026-10-30)
The owner runs a separate training tracker (Excel `Training_Tracker.xlsx`, Streamlit dashboard,
Telegram bot with Haiku parsing + confirm buttons, `habits.json`) in
`C:\Users\morit\OneDrive\Desktop\Zeug\08_Training`. Integrate it into MGPA once M5 (tools + HITL)
exists — the bot's "parse → show table → ✅ save / ❌ cancel" flow is exactly the M5 HITL pattern.
Sketch: Postgres tables for exercises (incl. gear settings, active flag), training sessions, sets,
habits; one-off import from the Excel; agent tools `log_training` (write, needs confirmation) and
`training_briefing` (read: last weights + gear settings per focus); training in the daily briefing
(M6); dashboard page in the frontend. Note: the PDF plan says "Schulterdrücken Maschine", the
CONTEXT.md/bot say "Schulterdrücken Kurzhantel" — ask the owner which is current.

## Planned extension: M5c Job applications tracker (after M5, owner request 2026-10-30)
Same "domain module" blueprint as training: table `applications` (company, role, status
draft → applied → interview → offer / rejected, dates, next step, contact; links to knowledge-base
documents like CV/cover letter), stats endpoint (counts per status, response rate, upcoming
deadlines — aggregated in SQL, not in the browser), agent tools (create/update with HITL
confirmation, read status), `/applications` page with a Kanban board + funnel chart, follow-up
reminders in the daily briefing (M6). Dashboards: one page per domain, no generic dashboard
builder. Charts: evaluate Chakra's chart package (Recharts-based, follows dark mode) when the first
dashboard is built.

## Planned extension: Telegram channel (after M7 deployment, owner request 2026-10-30)
Telegram as a second client of the same backend ("channel-agnostic core"): a thin bot container
on the VPS forwards messages to the MGPA API and maps HITL confirmations to inline buttons
(✅/❌). No business logic in the bot. Only the owner's Telegram user ID is allowed; bot token
via env. Needs the backend reachable 24/7, hence after M7. Frontend must be mobile-friendly
anyway (web UI on the phone as fallback).
