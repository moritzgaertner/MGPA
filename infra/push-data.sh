#!/usr/bin/env bash
# One-off: move your LOCAL data (database + uploaded documents) to the server, replacing the
# server's data. Run after the first deploy, before you start using the server version.
#
#   ./infra/push-data.sh
#
# Local: the dev Postgres from infra/docker-compose.yml must be running.
set -euo pipefail
HOST="${HOST:-root@2.31.156.148}"
DIR="${DIR:-/opt/mgpa}"
cd "$(dirname "$0")/.."
set -a; source .env; set +a  # local POSTGRES_USER / POSTGRES_DB
LOCAL="docker compose -f infra/docker-compose.yml --env-file .env"
REMOTE="cd $DIR && docker compose -f infra/compose.prod.yaml --env-file .env"

read -r -p "This REPLACES all data on $HOST with your local data. Continue? [y/N] " answer
[[ "$answer" == "y" ]] || exit 1

echo "== Stop server app containers (database keeps running)"
ssh "$HOST" "$REMOTE stop backend pipelines"

echo "== Copy database"
# Custom-format dump streamed over SSH; --clean drops the server's objects first.
$LOCAL exec -T postgres pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc --no-owner \
  | ssh "$HOST" "$REMOTE exec -T postgres sh -c 'pg_restore -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" --clean --if-exists --no-owner'"

if [[ -d data/documents ]]; then
  echo "== Copy uploaded documents"
  tar -C data/documents -cf - . \
    | ssh "$HOST" "$REMOTE run --rm -T --no-deps --entrypoint tar backend -C /data/documents -xf -"
fi

echo "== Start again"
ssh "$HOST" "$REMOTE up -d"
echo "Done."
