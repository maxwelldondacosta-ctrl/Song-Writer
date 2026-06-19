#!/usr/bin/env bash
# Server runner — used by both the launchd service and launch-app.sh.
# Starts uvicorn (background) + Next.js dev (foreground).
# When this script exits, uvicorn is killed via trap.

set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$HOME/.cargo/bin:$PATH"

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
WEB_PORT="${SONGWRITER_WEB_PORT:-3737}"
API_PORT="${SONGWRITER_API_PORT:-8000}"
LOG_DIR="$HOME/Library/Logs/Songwriter"

mkdir -p "$LOG_DIR"

cd "$REPO_DIR"

# Bootstrap one-time setup if needed
if [ ! -f data/songwriter.db ]; then
    echo "$(date)  Building database (first run)..."
    .venv/bin/songwriter-build
fi

if [ ! -d apps/web/node_modules ] || [ ! -d apps/web/node_modules/@dnd-kit ]; then
    echo "$(date)  Installing Node deps..."
    ( cd apps/web && npm install )
fi

# Kill anything on our ports from a previous crashed run
kill_port() {
    local port="$1"
    local pids
    pids=$(lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null || true)
    [ -n "$pids" ] && kill $pids 2>/dev/null || true
}
kill_port "$API_PORT"
kill_port "$WEB_PORT"

# Start API in background
echo "$(date)  Starting API on :$API_PORT"
.venv/bin/uvicorn songwriter.api.main:app \
    --port "$API_PORT" \
    --log-level warning \
    >> "$LOG_DIR/api.log" 2>&1 &
API_PID=$!

# Kill API when this script exits (launchd will restart the whole thing)
trap 'kill "$API_PID" 2>/dev/null; jobs -p | xargs -r kill 2>/dev/null' EXIT TERM INT

# Start Next.js dev in foreground — launchd tracks this process
echo "$(date)  Starting web on :$WEB_PORT"
cd apps/web
exec env PORT="$WEB_PORT" npm run dev >> "$LOG_DIR/web.log" 2>&1
