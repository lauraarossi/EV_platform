#!/usr/bin/env bash
# Stop the API and web dev servers. Leaves Postgres running (and your data
# intact); pass --db to stop the container too.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT/.dev-logs"

for name in api web; do
  pidfile="$LOG_DIR/$name.pid"
  if [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
    pkill -TERM -P "$(cat "$pidfile")" 2>/dev/null
    kill -TERM "$(cat "$pidfile")" 2>/dev/null
    echo "stopped $name"
  else
    echo "$name not running"
  fi
  rm -f "$pidfile"
done

if [ "${1:-}" = "--db" ]; then
  cd "$ROOT" && docker compose stop db && echo "stopped database (data preserved)"
fi
