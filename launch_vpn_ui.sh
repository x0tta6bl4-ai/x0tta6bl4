#!/usr/bin/env bash
# x0tta6bl4 VPN UI Launcher (Robust Version 2)

LOG_FILE="/tmp/x0tta6bl4_vpn.log"
echo "--- Launching Robust V2 at $(date) ---" >> "$LOG_FILE"

PROJECT_ROOT="/mnt/projects"
cd "$PROJECT_ROOT" || { echo "Failed to cd to $PROJECT_ROOT" >> "$LOG_FILE"; exit 1; }

# Kill previous app instances
pkill -f x0tta6bl4_vpn_app.py || true

# Start backend
# Using 127.0.0.1 explicitly
nohup python3 x0tta6bl4_vpn_app.py >> "$LOG_FILE" 2>&1 &
BACKEND_PID=$!
echo "Backend started with PID $BACKEND_PID" >> "$LOG_FILE"

# Wait for port 8089 to be ready
for i in {1..20}; do
    if lsof -i :8089 > /dev/null; then
        echo "Port 8089 is ready after $i attempts" >> "$LOG_FILE"
        break
    fi
    sleep 0.5
done

# Try to open the browser
URL="http://127.0.0.1:8089"
echo "Opening $URL" >> "$LOG_FILE"

if command -v xdg-open > /dev/null; then
    xdg-open "$URL" >> "$LOG_FILE" 2>&1
elif [ -n "$DISPLAY" ]; then
    google-chrome --app="$URL" >> "$LOG_FILE" 2>&1 || firefox "$URL" >> "$LOG_FILE" 2>&1
else
    echo "No display or browser found" >> "$LOG_FILE"
fi

# Disown and exit launcher
disown $BACKEND_PID
echo "Launcher V2 finished." >> "$LOG_FILE"
