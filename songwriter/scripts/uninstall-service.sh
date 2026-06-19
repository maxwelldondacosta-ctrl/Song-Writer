#!/usr/bin/env bash
# Remove the Songwriter background service.

set -euo pipefail

PLIST_LABEL="com.songwriter.servers"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_LABEL}.plist"

echo
echo "  Removing Songwriter service..."

if launchctl list "$PLIST_LABEL" &>/dev/null; then
    launchctl bootout "gui/$(id -u)/${PLIST_LABEL}" 2>/dev/null \
        || launchctl unload -w "$PLIST_PATH" 2>/dev/null \
        || true
    echo "  Service stopped."
else
    echo "  Service was not running."
fi

[ -f "$PLIST_PATH" ] && rm "$PLIST_PATH" && echo "  Plist removed."
SUPPORT_SERVICE="$HOME/Library/Application Support/Songwriter/service.sh"
[ -f "$SUPPORT_SERVICE" ] && rm "$SUPPORT_SERVICE" && echo "  Service runner removed."

echo
echo "  Songwriter servers will no longer start at login."
echo "  To use the app, run ./start.sh or reinstall with ./scripts/install-service.sh"
echo
