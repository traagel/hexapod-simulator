#!/usr/bin/env bash
set -euo pipefail

DEVICE="${1:-}"
HOST="0.0.0.0"
WS_PORT=8765
HTTP_PORT=8080
DIR="$(cd "$(dirname "$0")/.." && pwd)"

cleanup() {
    echo "shutting down..."
    kill "$WS_PID" "$HTTP_PID" 2>/dev/null
    wait "$WS_PID" "$HTTP_PID" 2>/dev/null
}
trap cleanup EXIT INT TERM

cd "$DIR"

# websocket server
if [ -n "$DEVICE" ]; then
    uv run python server.py --device "$DEVICE" --host "$HOST" --port "$WS_PORT" &
else
    uv run python server.py --host "$HOST" --port "$WS_PORT" &
fi
WS_PID=$!

# static file server for the frontend
python -m http.server "$HTTP_PORT" --bind "$HOST" -d frontend &
HTTP_PID=$!

echo "frontend:  http://$HOST:$HTTP_PORT"
echo "websocket: ws://$HOST:$WS_PORT"
echo "pid ws=$WS_PID http=$HTTP_PID — ctrl-c to stop"

wait
