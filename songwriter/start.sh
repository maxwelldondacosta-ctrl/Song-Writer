#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

WEB_PORT="${SONGWRITER_WEB_PORT:-3737}"
API_PORT="${SONGWRITER_API_PORT:-8000}"
APP_URL="http://localhost:${WEB_PORT}"

# Force the Tauri app to load the Next.js dev server at our chosen port even if
# tauri.conf.json's devUrl is overridden by env / older config.
export TAURI_DEV_URL="$APP_URL"

# Two modes:
#   ./start.sh         → runs API + Next.js + opens browser (default)
#   ./start.sh --tauri → also launches the Tauri desktop window
USE_TAURI=0
for arg in "$@"; do
  if [ "$arg" = "--tauri" ]; then
    USE_TAURI=1
  fi
done

# ---------- bootstrap (one-time) ----------

bootstrap_rust() {
  if command -v cargo >/dev/null 2>&1; then
    return 0
  fi
  echo
  echo "  Tauri needs the Rust toolchain. Installing rustc + cargo via Homebrew..."
  echo "  (~5 minutes the first time. Re-runs are instant.)"
  echo
  if command -v brew >/dev/null 2>&1; then
    brew install rust
  else
    echo "  Homebrew not found. Falling back to rustup install (curl-based)."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable --profile minimal
    # rustup installs to ~/.cargo/bin which we need on PATH
    export PATH="$HOME/.cargo/bin:$PATH"
  fi
}

bootstrap_node_deps() {
  # Run npm install if node_modules is missing OR if the Tauri CLI is missing
  # (the latter happens when @tauri-apps/cli was added after a previous install).
  if [ ! -d apps/web/node_modules ] \
      || [ ! -x apps/web/node_modules/.bin/tauri ] \
      || [ ! -d apps/web/node_modules/@dnd-kit ]; then
    echo "  Installing / refreshing Node deps..."
    ( cd apps/web && npm install )
  fi
}

bootstrap_python_db() {
  if [ ! -f data/songwriter.db ]; then
    echo "  Database missing — building from seeds (one-time, ~5s)..."
    ./.venv/bin/songwriter-build
  fi
}

# ---------- launch helpers ----------

trap 'jobs -p | xargs -r kill 2>/dev/null' EXIT

# Kill any leftover servers on our ports from a previous failed run
kill_port() {
  local port="$1"
  local pids
  pids=$(lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "  cleaning up stale process on :$port (pids: $pids)"
    kill $pids 2>/dev/null || true
    sleep 0.4
  fi
}
kill_port "$API_PORT"
kill_port "$WEB_PORT"

start_api() {
  ./.venv/bin/uvicorn songwriter.api.main:app --port "$API_PORT" &
  API_PID=$!
}

start_next_dev() {
  ( cd apps/web && PORT="$WEB_PORT" npm run dev ) &
  WEB_PID=$!
}

wait_for_url() {
  local url="$1"
  local tries="${2:-60}"
  for _ in $(seq 1 "$tries"); do
    if curl -sf "$url" -o /dev/null 2>/dev/null; then
      return 0
    fi
    sleep 0.5
  done
  return 1
}

start_tauri() {
  ( cd apps/web && npm run tauri:dev ) &
  TAURI_PID=$!
}

open_browser_fallback() {
  if [ -d "/Applications/Google Chrome.app" ]; then
    open -na "Google Chrome" --args --app="$APP_URL" --new-window 2>/dev/null && return
  fi
  open "$APP_URL" 2>/dev/null || true
}

# ---------- run ----------

bootstrap_python_db
bootstrap_node_deps

if [ "$USE_TAURI" -eq 1 ]; then
  bootstrap_rust
fi

start_api
start_next_dev

# Wait for Next dev server before pointing the window at it.
if ! wait_for_url "$APP_URL" 80; then
  echo "  ⚠  Web server didn't come up in 40s. Check the logs above."
fi

if [ "$USE_TAURI" -eq 1 ]; then
  echo
  echo "  Starting the Songwriter desktop window..."
  echo "  First run compiles Rust deps (~3-5 min). Subsequent runs are instant."
  echo
  start_tauri
else
  open_browser_fallback
fi

sleep 1

cat <<EOF

==============================================================
  SONGWRITER — running

  →  App:           ${APP_URL}
  →  API:           http://localhost:${API_PORT}
  →  API health:    http://localhost:${API_PORT}/healthz

  Mode: $( [ "$USE_TAURI" -eq 1 ] && echo "Tauri desktop window (--tauri)" || echo "browser" )
  Override port:    SONGWRITER_WEB_PORT=4242 ./start.sh
  Tauri window:     ./start.sh --tauri
  Ctrl+C to stop.
==============================================================
EOF

wait
