#!/usr/bin/env bash
# Start Eevie locally: database, API, and web app.
#
#   ./scripts/start-dev.sh
#
# Requires Docker Desktop to be running on Windows with WSL integration enabled
# for this distro (Settings -> Resources -> WSL Integration). That setting is
# reset by a Docker Desktop reinstall, so if `docker` is missing, check there.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONDA_ENV="${CONDA_ENV:-EV_Env}"
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-5173}"
LOG_DIR="$ROOT/.dev-logs"
mkdir -p "$LOG_DIR"

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$1"; }
die() { printf '\n\033[1;31mERROR: %s\033[0m\n' "$1" >&2; exit 1; }

# --- python from the conda env, without needing `conda activate` -------------
PY="$HOME/miniconda3/envs/$CONDA_ENV/bin/python"
[ -x "$PY" ] || die "Python not found at $PY. Is the '$CONDA_ENV' conda env created?"
BIN="$(dirname "$PY")"

command -v docker >/dev/null 2>&1 \
  || die "docker not found. Start Docker Desktop and enable WSL integration for this distro."

# --- 1. database -------------------------------------------------------------
say "Starting Postgres"
cd "$ROOT"
docker compose up -d db

printf '    waiting for it to be healthy'
for _ in $(seq 1 60); do
  status="$(docker inspect --format '{{.State.Health.Status}}' ev_platform-db-1 2>/dev/null || echo starting)"
  [ "$status" = "healthy" ] && { printf ' ok\n'; break; }
  printf '.'; sleep 1
done
[ "${status:-}" = "healthy" ] || die "Postgres did not become healthy. Try: docker compose logs db"

# --- 2. schema ---------------------------------------------------------------
say "Applying migrations"
cd "$ROOT/backend"
[ -f .env ] || { cp .env.example .env; echo "    created backend/.env from the example"; }
"$BIN/alembic" upgrade head

# --- 3. API ------------------------------------------------------------------
say "Starting API on :$API_PORT"
if curl -sf "http://localhost:$API_PORT/api/v1/health" >/dev/null 2>&1; then
  echo "    already running"
else
  nohup "$BIN/uvicorn" app.main:app --reload --port "$API_PORT" \
    > "$LOG_DIR/api.log" 2>&1 &
  echo "$!" > "$LOG_DIR/api.pid"
fi

# --- 4. web ------------------------------------------------------------------
say "Starting web app on :$WEB_PORT"
cd "$ROOT/frontend"
[ -d node_modules ] || { echo "    installing dependencies"; npm install; }
if curl -sf "http://localhost:$WEB_PORT/" >/dev/null 2>&1; then
  echo "    already running"
else
  nohup npm run dev -- --port "$WEB_PORT" > "$LOG_DIR/web.log" 2>&1 &
  echo "$!" > "$LOG_DIR/web.pid"
fi

# --- 5. wait and report ------------------------------------------------------
printf '\n    waiting for both to answer'
for _ in $(seq 1 60); do
  api=$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:$API_PORT/api/v1/health" || true)
  web=$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:$WEB_PORT/" || true)
  [ "$api" = "200" ] && [ "$web" = "200" ] && { printf ' ok\n'; break; }
  printf '.'; sleep 1
done

if [ "${api:-}" = "200" ] && [ "${web:-}" = "200" ]; then
  cat <<EOF

  Eevie is up.

    app   http://localhost:$WEB_PORT
    docs  http://localhost:$API_PORT/docs
    logs  $LOG_DIR/{api,web}.log

  Stop with: ./scripts/stop-dev.sh
EOF
else
  die "api=$api web=$web — check $LOG_DIR/api.log and $LOG_DIR/web.log"
fi
