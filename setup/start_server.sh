#!/bin/bash
# Richtet den Uni-Agent Server als permanenten macOS LaunchAgent ein.
# Der Server startet beim Login automatisch und wird bei Absturz neu gestartet.

PLIST_NAME="com.uniagent.server"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"
PYTHON_PATH=$(which python3)
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$HOME/logs"

mkdir -p "$LOG_DIR"

cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$PLIST_NAME</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON_PATH</string>
        <string>$SCRIPT_DIR/server.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$SCRIPT_DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$LOG_DIR/uni-agent-server.log</string>
    <key>StandardErrorPath</key>
    <string>$LOG_DIR/uni-agent-server-error.log</string>
    <key>ThrottleInterval</key>
    <integer>10</integer>
</dict>
</plist>
EOF

launchctl unload "$PLIST_PATH" 2>/dev/null
launchctl load "$PLIST_PATH"
echo "Server-LaunchAgent installiert und gestartet."
echo "Logs:      $LOG_DIR/uni-agent-server.log"
echo "Stoppen:   launchctl unload $PLIST_PATH"
echo "Starten:   launchctl load $PLIST_PATH"
