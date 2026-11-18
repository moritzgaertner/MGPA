#!/usr/bin/env bash
# One-off: create the server's secret file /opt/mgpa/.env from your local .env.
#
#   ./infra/server-env.sh            # refuses if the server already has one
#   ./infra/server-env.sh --force    # overwrite (e.g. after rotating an API key)
#
# Copies API keys and the login (same username/password as locally), but uses its OWN
# database password and session secret for production (generated once, kept on --force).
# Nothing is printed; the file is readable by root only.
set -euo pipefail
HOST="${HOST:-root@2.31.156.148}"
DIR="${DIR:-/opt/mgpa}"
cd "$(dirname "$0")/.."

[[ -f .env ]] || { echo "No local .env found." >&2; exit 1; }
if ! grep -qE "^AUTH_PASSWORD_HASH='?\\\$argon2" .env; then
  echo "Set your login first:  cd backend && uv run python -m mgpa_backend.auth" >&2
  exit 1
fi
if [[ "${1:-}" != "--force" ]] && ssh "$HOST" "test -f $DIR/.env"; then
  echo "$HOST:$DIR/.env exists already (use --force to overwrite)." >&2
  exit 1
fi

# Everything except values that differ in production (those are set below / by compose).
env_body=$(grep -vE '^(POSTGRES_PASSWORD|POSTGRES_PORT|DATABASE_URL|SESSION_SECRET|APP_ENV|DOCUMENTS_DIR)=' .env)

# Keep the server's own secrets when overwriting: the database volume only accepts the password
# it was created with, and a new session secret would log you out.
existing() { ssh "$HOST" "grep -s '^$1=' $DIR/.env | cut -d= -f2-" || true; }
db_password=$(existing POSTGRES_PASSWORD)
session_secret=$(existing SESSION_SECRET)
db_password=${db_password:-$(openssl rand -hex 32)}
session_secret=${session_secret:-$(openssl rand -hex 32)}

ssh "$HOST" "mkdir -p $DIR && umask 077 && cat > $DIR/.env" <<EOF
$env_body

# --- production values (generated once by infra/server-env.sh, kept on --force) ---
POSTGRES_PASSWORD=$db_password
SESSION_SECRET=$session_secret
APP_ENV=production
EOF
echo "Created $HOST:$DIR/.env"
