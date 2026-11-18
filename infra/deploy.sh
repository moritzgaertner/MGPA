#!/usr/bin/env bash
# Deploy the current code to the server: copy it, build the images there, restart changed
# containers. Data (database, documents) lives in Docker volumes and is not touched.
#
#   ./infra/deploy.sh        (run in WSL from anywhere in the repo)
#
# Server layout: /opt/mgpa = copy of this repo + .env (secrets, see infra/server-env.sh).
# The shared Caddy (in /opt/kirchstrasse16, Wichtel project) routes the MGPA hostname to the
# `web` container over the Docker network "edge".
set -euo pipefail
HOST="${HOST:-root@2.31.156.148}"
DIR="${DIR:-/opt/mgpa}"
SSH_OPTS="${SSH_OPTS:-}"
cd "$(dirname "$0")/.."

echo "== Copy code to $HOST:$DIR"
# --filter 'P .env' protects the server's secrets from --delete.
rsync -az --delete -e "ssh $SSH_OPTS" \
  --filter 'P .env' \
  --exclude .git --exclude .env --exclude 'data/' \
  --exclude node_modules --exclude .venv --exclude dist \
  --exclude __pycache__ --exclude .mypy_cache --exclude .ruff_cache --exclude .pytest_cache \
  --exclude .dagster_home \
  ./ "$HOST:$DIR/"

echo "== Build and start"
# shellcheck disable=SC2029  # $DIR is meant to expand locally
ssh $SSH_OPTS "$HOST" "set -e
  cd $DIR
  test -f .env || { echo 'Missing $DIR/.env - run infra/server-env.sh first' >&2; exit 1; }
  docker network inspect edge >/dev/null 2>&1 || docker network create edge
  docker compose -f infra/compose.prod.yaml --env-file .env up -d --build --remove-orphans
  docker image prune -f >/dev/null
  docker compose -f infra/compose.prod.yaml --env-file .env ps"
