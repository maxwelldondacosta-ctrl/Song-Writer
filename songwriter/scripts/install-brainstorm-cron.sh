#!/usr/bin/env bash
# Install the autonomous brainstorm agent as a macOS launchd User Agent.
# Fires every 20 minutes, calls Claude Sonnet, appends ideas to docs/brainstorm-log.md.
# Runs in the background — no Claude session needed.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PLIST_LABEL="com.songwriter.brainstorm"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_LABEL}.plist"
SUPPORT_DIR="$HOME/Library/Application Support/Songwriter"
AGENT_SRC="$REPO_DIR/scripts/brainstorm-agent.py"
AGENT_DST="$SUPPORT_DIR/brainstorm-agent.py"
LOG_DIR="$HOME/Library/Logs/Songwriter"
# Use Homebrew Python — script is stdlib-only so no venv needed,
# and /opt/homebrew is TCC-safe (not under ~/Desktop).
PYTHON="/opt/homebrew/bin/python3"

echo
echo "  Installing Songwriter brainstorm agent..."
echo "  Fires every 20 minutes — no Claude session needed."
echo

mkdir -p "$SUPPORT_DIR" "$LOG_DIR"

# Copy agent to TCC-safe location with REPO_DIR hardcoded
sed "s|/Users/mdacosta/Desktop/Song Writing/songwriter|$REPO_DIR|g" \
    "$AGENT_SRC" > "$AGENT_DST"
chmod +x "$AGENT_DST"

# Unload old version if running
launchctl bootout "gui/$(id -u)/${PLIST_LABEL}" 2>/dev/null || true

cat > "$PLIST_PATH" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_LABEL}</string>

    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON}</string>
        <string>${AGENT_DST}</string>
    </array>

    <!-- Fire every hour -->
    <key>StartInterval</key>
    <integer>3600</integer>

    <key>StandardOutPath</key>
    <string>${LOG_DIR}/brainstorm.log</string>
    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/brainstorm.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>HOME</key>
        <string>${HOME}</string>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
PLIST

launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH"

echo "  Agent installed. First run in ≤20 minutes."
echo "  Ideas log:  $REPO_DIR/docs/brainstorm-log.md"
echo "  Agent log:  $LOG_DIR/brainstorm.log"
echo
echo "  To stop:  launchctl bootout gui/$(id -u)/${PLIST_LABEL}"
echo "  To tail:  tail -f $LOG_DIR/brainstorm.log"
echo
