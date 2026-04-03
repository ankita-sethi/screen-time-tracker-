#!/bin/bash
# Uninstall Screen Time Tracker

set -e

PLIST_DIR="$HOME/Library/LaunchAgents"

echo "Stopping services..."
launchctl unload "$PLIST_DIR/com.screentime.tracker.plist" 2>/dev/null || true
launchctl unload "$PLIST_DIR/com.screentime.dashboard.plist" 2>/dev/null || true
launchctl unload "$PLIST_DIR/com.screentime.morning-open.plist" 2>/dev/null || true

echo "Removing launchd agents..."
rm -f "$PLIST_DIR/com.screentime.tracker.plist"
rm -f "$PLIST_DIR/com.screentime.dashboard.plist"
rm -f "$PLIST_DIR/com.screentime.morning-open.plist"

echo ""
echo "✓ Uninstalled. Services stopped and removed."
echo "  Your data (screentime.db) is still in this folder if you want it."
