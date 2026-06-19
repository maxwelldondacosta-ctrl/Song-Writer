#!/usr/bin/env bash
# Install Songwriter as a macOS login item (launchd User Agent).
#
# macOS TCC restricts launchd background agents from accessing ~/Desktop and
# ~/Documents. To work around this, the plist uses `/usr/bin/open -g` to launch
# Songwriter.app at login. The app runs in the user's GUI session (full Desktop
# access) and detects headless mode via a flag file to start servers without
# opening a Chrome window.
#
# After running this:
#   - Servers start automatically at login (no Terminal, no Chrome popup)
#   - Songwriter.app just opens the window — no Terminal, no start.sh
#   - Logs: ~/Library/Logs/Songwriter/
#   - To remove: ./scripts/uninstall-service.sh

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PLIST_LABEL="com.songwriter.servers"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_LABEL}.plist"
LOG_DIR="$HOME/Library/Logs/Songwriter"
APP_PATH="$REPO_DIR/Songwriter.app"
HEADLESS_FLAG="$HOME/.songwriter-headless-boot"

echo
echo "  Installing Songwriter service..."
echo "  Repo:  $REPO_DIR"
echo "  Plist: $PLIST_PATH"
echo "  Logs:  $LOG_DIR"
echo

# Make scripts executable
chmod +x "$REPO_DIR/scripts/service.sh"
chmod +x "$REPO_DIR/scripts/launch-app.sh"
chmod +x "$REPO_DIR/scripts/build-app.sh"
chmod +x "$REPO_DIR/scripts/uninstall-service.sh"

# Create log directory
mkdir -p "$LOG_DIR"

# Unload any existing version so we can replace it cleanly
if launchctl list "$PLIST_LABEL" &>/dev/null; then
    echo "  Removing old service..."
    launchctl bootout "gui/$(id -u)/${PLIST_LABEL}" 2>/dev/null \
        || launchctl unload -w "$PLIST_PATH" 2>/dev/null \
        || true
fi

# Build the app first so the plist can reference it
echo "  Rebuilding Songwriter.app..."
"$REPO_DIR/scripts/build-app.sh"

# Write the launchd plist.
# Strategy: plist creates the headless flag then calls `open -g Songwriter.app`.
# The app launches in the GUI session (no TCC restrictions) and launch-app.sh
# detects the flag to start servers without opening a Chrome window.
cat > "$PLIST_PATH" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_LABEL}</string>

    <!-- Create the headless flag then open the app in the GUI session so
         macOS TCC grants it full Desktop/Documents access. -->
    <key>ProgramArguments</key>
    <array>
        <string>/bin/sh</string>
        <string>-c</string>
        <string>touch "${HEADLESS_FLAG}" &amp;&amp; /usr/bin/open -g "${APP_PATH}"</string>
    </array>

    <!-- Trigger once at login; no KeepAlive — the app manages server restarts. -->
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>

    <key>StandardOutPath</key>
    <string>${LOG_DIR}/service.log</string>
    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/service.log</string>
</dict>
</plist>
PLIST

# Load the service
launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH" 2>/dev/null \
    || launchctl load -w "$PLIST_PATH"

echo "  Login item installed."
echo

echo
echo "============================================================"
echo "  Done!"
echo
echo "  → Double-click Songwriter.app to use the app"
echo "  → Servers start automatically at login (no Chrome popup)"
echo "  → Logs: $LOG_DIR/"
echo
echo "  To remove auto-start:"
echo "    ./scripts/uninstall-service.sh"
echo "============================================================"
echo
