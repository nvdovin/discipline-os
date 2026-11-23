#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

# Long polling is used instead of webhooks, so no public HTTPS is required
# for local development. Auto-reload is opt-in because two bot pollers must
# never run at the same time.
if [[ "${RELOAD:-0}" == "1" ]]; then
  exec python3 -m uvicorn app.main:app --host "$HOST" --port "$PORT" --reload
fi

exec python3 -m uvicorn app.main:app --host "$HOST" --port "$PORT"
