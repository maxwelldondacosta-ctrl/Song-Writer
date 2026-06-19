#!/usr/bin/env bash
# Builds Songwriter.app — a clickable Mac app that launches start.sh in the
# background so the Tauri window appears with no Terminal visible.
#
# Run this once: ./scripts/build-app.sh
# It produces Songwriter.app in the repo root. Drag it to /Applications or
# the Dock for one-click access.

set -euo pipefail
cd "$(dirname "$0")/.."
REPO_DIR="$(pwd)"

OUT="$REPO_DIR/Songwriter.app"

# Remove old build
rm -rf "$OUT"

# AppleScript source — smart launcher:
#   - If servers already up: opens the window immediately
#   - If not: starts the service/servers, then opens the window
#   - Never shows a Terminal
read -r -d '' SRC <<APPLESCRIPT || true
on run
	do shell script "bash '$REPO_DIR/scripts/launch-app.sh' > /dev/null 2>&1 &"
end run
APPLESCRIPT

# Compile to .app bundle
TMP_SCRIPT="$(mktemp -t songwriter-applescript)"
trap 'rm -f "$TMP_SCRIPT"' EXIT
printf '%s\n' "$SRC" > "$TMP_SCRIPT"

osacompile -o "$OUT" "$TMP_SCRIPT"

# Replace the default AppleScript icon with ours
ICON_SRC="$REPO_DIR/apps/web/src-tauri/icons/icon.png"
ICON_DST_DIR="$OUT/Contents/Resources"
if [ -f "$ICON_SRC" ] && [ -d "$ICON_DST_DIR" ]; then
  # AppleScript-generated apps use applet.icns. Convert PNG → ICNS via sips.
  TMP_ICONSET="$(mktemp -d)"
  trap 'rm -rf "$TMP_ICONSET"; rm -f "$TMP_SCRIPT"' EXIT
  for size in 16 32 64 128 256 512; do
    sips -z "$size" "$size" "$ICON_SRC" --out "$TMP_ICONSET/icon_${size}x${size}.png" >/dev/null 2>&1 || true
  done
  iconutil -c icns "$TMP_ICONSET" -o "$ICON_DST_DIR/applet.icns" 2>/dev/null || true
  # iconutil requires a .iconset directory naming convention; if it failed, fall back.
  if [ ! -f "$ICON_DST_DIR/applet.icns" ]; then
    cp "$ICON_SRC" "$ICON_DST_DIR/applet.icns" 2>/dev/null || true
  fi
fi

# Update Info.plist with a friendlier display name
PLIST="$OUT/Contents/Info.plist"
if [ -f "$PLIST" ]; then
  /usr/libexec/PlistBuddy -c "Set :CFBundleName Songwriter" "$PLIST" 2>/dev/null || true
  /usr/libexec/PlistBuddy -c "Set :CFBundleDisplayName Songwriter" "$PLIST" 2>/dev/null || true
fi

echo
echo "  ✓ Built $OUT"
echo
echo "  Drag Songwriter.app to /Applications (or your Dock)."
echo "  Double-click it any time — no Terminal needed."
echo
echo "  Tip: run ./scripts/install-service.sh once to make servers"
echo "  start automatically at login (then the app opens instantly)."
echo
echo "  Logs: ~/Library/Logs/Songwriter/"
