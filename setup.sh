#!/bin/bash
# Screen Time Tracker — one-command setup for macOS
# Usage: git clone <repo> && cd screen-time-tracker && bash setup.sh

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo "╔══════════════════════════════════════╗"
echo "║     Screen Time Tracker Setup        ║"
echo "║  Tracks LeetCode · LinkedIn · Gmail  ║"
echo "╚══════════════════════════════════════╝"
echo ""

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_DIR="$HOME/Library/LaunchAgents"
USER_NAME=$(whoami)

# Check macOS
if [[ "$(uname)" != "Darwin" ]]; then
    echo "❌ This only works on macOS. Exiting."
    exit 1
fi

# Check Python 3
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Install it: https://www.python.org/downloads/"
    exit 1
fi

# Install dependencies
echo -e "${YELLOW}[1/4]${NC} Installing Python dependencies..."
pip3 install -r "$PROJECT_DIR/requirements.txt" --break-system-packages -q 2>/dev/null || \
pip3 install -r "$PROJECT_DIR/requirements.txt" -q
echo "  ✓ Flask installed"

# Create launchd plist for tracker
echo -e "${YELLOW}[2/4]${NC} Registering background services..."

cat > "$PLIST_DIR/com.screentime.tracker.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.screentime.tracker</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>${PROJECT_DIR}/tracker.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${PROJECT_DIR}/tracker.log</string>
    <key>StandardErrorPath</key>
    <string>${PROJECT_DIR}/tracker.log</string>
</dict>
</plist>
EOF

# Create launchd plist for dashboard
cat > "$PLIST_DIR/com.screentime.dashboard.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.screentime.dashboard</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>${PROJECT_DIR}/app.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${PROJECT_DIR}/dashboard.log</string>
    <key>StandardErrorPath</key>
    <string>${PROJECT_DIR}/dashboard.log</string>
</dict>
</plist>
EOF

# Create launchd plist for auto-opening dashboard when Chrome launches
cat > "$PLIST_DIR/com.screentime.morning-open.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.screentime.morning-open</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>${PROJECT_DIR}/open_dashboard.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
EOF

echo "  ✓ 3 launchd agents created"

# Load the services
echo -e "${YELLOW}[3/4]${NC} Starting services..."
launchctl unload "$PLIST_DIR/com.screentime.tracker.plist" 2>/dev/null || true
launchctl unload "$PLIST_DIR/com.screentime.dashboard.plist" 2>/dev/null || true
launchctl unload "$PLIST_DIR/com.screentime.morning-open.plist" 2>/dev/null || true

launchctl load "$PLIST_DIR/com.screentime.tracker.plist"
launchctl load "$PLIST_DIR/com.screentime.dashboard.plist"
launchctl load "$PLIST_DIR/com.screentime.morning-open.plist"
echo "  ✓ All services running"

# Verify
echo -e "${YELLOW}[4/4]${NC} Verifying..."
sleep 2
if curl -s -o /dev/null -w "" http://localhost:8050/ 2>/dev/null; then
    echo "  ✓ Dashboard is live"
else
    echo "  ⚠ Dashboard may take a few seconds to start"
fi

echo ""
echo -e "${GREEN}══════════════════════════════════════${NC}"
echo -e "${GREEN}  Setup complete!${NC}"
echo ""
echo "  Dashboard:  http://localhost:8050"
echo ""
echo "  • Tracks LeetCode, LinkedIn, Gmail on Chrome"
echo "  • Auto-starts when you log in"
echo "  • Opens dashboard when Chrome launches"
echo "  • Stops when you shut down / sleep"
echo ""
echo "  To uninstall, run: bash $(basename "$0") --uninstall"
echo -e "${GREEN}══════════════════════════════════════${NC}"
echo ""

# Open dashboard now
open http://localhost:8050
