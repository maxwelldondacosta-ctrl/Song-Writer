#!/usr/bin/env bash
# Called by Songwriter.app on double-click, and indirectly at login via launchd.
#
# Normal (user click):   start servers if needed, then open Chrome window.
# Headless (login boot): start servers in background, no Chrome window.
#   Headless mode is signaled by the presence of ~/.songwriter-headless-boot.
#   The launchd plist creates that file and calls `open -g Songwriter.app`.

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/sbin:/usr/sbin:$HOME/.cargo/bin:$PATH"

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_URL="http://localhost:${SONGWRITER_WEB_PORT:-3737}"
API_URL="http://localhost:${SONGWRITER_API_PORT:-8000}"
LOG="$HOME/Library/Logs/Songwriter/app.log"
HEADLESS_FLAG="$HOME/.songwriter-headless-boot"

mkdir -p "$(dirname "$LOG")"

# Detect headless mode (login auto-start) and consume the flag
HEADLESS=false
if [ -f "$HEADLESS_FLAG" ]; then
    HEADLESS=true
    rm -f "$HEADLESS_FLAG"
fi

open_window() {
    if [ -d "/Applications/Google Chrome.app" ]; then
        open -na "Google Chrome" --args --app="$APP_URL" --new-window 2>/dev/null && return
    fi
    open "$APP_URL" 2>/dev/null || true
}

wait_for_api() {
    local tries="${1:-30}"
    for _ in $(seq 1 "$tries"); do
        curl -sf "$API_URL/healthz" -o /dev/null 2>/dev/null && return 0
        sleep 1
    done
    return 1
}

echo "=== Songwriter open $(date) headless=$HEADLESS ===" >> "$LOG"

# Fast path: servers already up
if curl -sf "$API_URL/healthz" -o /dev/null 2>/dev/null; then
    echo "  Servers up — $([ "$HEADLESS" = true ] && echo 'background boot done.' || echo 'opening window.')" >> "$LOG"
    [ "$HEADLESS" = false ] && open_window
    exit 0
fi

echo "  Servers not running — starting..." >> "$LOG"

# Start the servers
bash "$REPO_DIR/scripts/service.sh" >> "$LOG" 2>&1 &

# Wait for API (up to 60s for first-run Next.js compile)
if wait_for_api 60; then
    echo "  Ready — $([ "$HEADLESS" = true ] && echo 'background boot done.' || echo 'opening window.')" >> "$LOG"
    [ "$HEADLESS" = false ] && open_window
else
    echo "  Timed out waiting for servers." >> "$LOG"
    [ "$HEADLESS" = false ] && open_window
fi
