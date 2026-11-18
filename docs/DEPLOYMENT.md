# Deployment

MGPA runs on a small Hetzner VPS (2 vCPU, 4 GB RAM) next to another app ("Wichtel").

```
Internet ─► shared Caddy :80/:443 (HTTPS, /opt/kirchstrasse16, Wichtel project)
              ├─ wichteln.2-31-156-148.sslip.io ─► wichteln:3000
              └─ mgpa.2-31-156-148.sslip.io     ─► mgpa-web:80   (Docker network "edge")

/opt/mgpa (this repo + .env), compose project "mgpa":
  web        Caddy: static frontend + /api → backend
  backend    FastAPI (runs `alembic upgrade head` on start)
  pipelines  Dagster daemon (document ingestion sensor), no web UI
  postgres   Postgres 18 + pgvector, internal network only
```

**Why a separate project:** the Wichtel deploy script runs `docker compose up --remove-orphans`
on its own compose file. If MGPA's services lived in that file only on the server, the next Wichtel
deploy would remove them. As a separate project, either app can be deployed without touching the
other; the shared Caddy only needs one hostname block and the `edge` network.

**Hostname:** `sslip.io` resolves `mgpa.2-31-156-148.sslip.io` to `2.31.156.148` — no domain
purchase, and Caddy still gets a Let's Encrypt certificate.

## First deployment (once)

Run in WSL from the repo root, with SSH access to `root@2.31.156.148`.

1. Login for the app (if not done yet): `cd backend && uv run python -m mgpa_backend.auth`
2. Server secrets: `./infra/server-env.sh` — creates `/opt/mgpa/.env` from the local `.env`
   (same API keys and login, new database password and session secret).
3. Deploy MGPA: `./infra/deploy.sh` (creates the `edge` network; first build takes a few minutes).
4. Copy local data: `./infra/push-data.sh` (database + uploaded documents; asks for confirmation).
5. Route the hostname: in the Wichtel project run `./deploy/deploy.sh` (its Caddyfile contains the
   MGPA block, its Caddy joins `edge`). Caddy restarts → Wichtel is unavailable for a few seconds.
6. Open `https://mgpa.2-31-156-148.sslip.io` on the phone → share menu → "Add to Home Screen".

## Later deployments

- **Manually:** `./infra/deploy.sh`
- **Automatically:** `.github/workflows/deploy.yml` deploys every commit on `main` after CI passed.
  It is skipped until these repository secrets exist:

  ```bash
  ssh-keygen -t ed25519 -N '' -C mgpa-deploy -f ~/.ssh/mgpa_deploy
  ssh-copy-id -i ~/.ssh/mgpa_deploy.pub root@2.31.156.148
  gh secret set DEPLOY_SSH_KEY < ~/.ssh/mgpa_deploy
  ssh-keyscan -t ed25519 2.31.156.148 | gh secret set DEPLOY_KNOWN_HOSTS
  ```

  Trade-off: this key has root access to the server. Acceptable for a single-user hobby server;
  in a team setup, use a dedicated non-root deploy user in the `docker` group.

## Operations

```bash
ssh root@2.31.156.148
cd /opt/mgpa && C="docker compose -f infra/compose.prod.yaml --env-file .env"
$C ps                       # status
$C logs -f backend          # logs (also: pipelines, web, postgres)
$C exec postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > backup.dump  # backup
```

Changing an API key or the login: change it in the local `.env`, then
`./infra/server-env.sh --force` (keeps the server's database password and session secret) and
`./infra/deploy.sh`.

**Memory budget** (4 GB total): Postgres ~100 MB, backend ~200 MB, Dagster daemon ~300 MB,
Caddy ~30 MB each — well within limits. The Dagster web UI is left out on purpose; inspect
pipeline runs locally with `dagster dev`.

**Costs:** no extra server (shared VPS). Running costs: Anthropic API per token, Voyage
embeddings (200M tokens free), Langfuse Hobby (free).
