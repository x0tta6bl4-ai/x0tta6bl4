#!/bin/bash
# Simple HTTP server for demo dashboard
# Usage: ./START_DEMO_SERVER.sh

cd /mnt/AC74CC2974CBF3DC

# Check if port 8000 is already in use
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "⚠️ Port 8000 is already in use. Killing existing process..."
    pkill -f "python.*8000" || pkill -f "http.server.*8000" || true
    sleep 2
fi

echo "=== 🚀 Starting Demo Server on port 8000 ==="
echo ""
echo "Dashboard will be available at:"
echo "  http://localhost:8000/causal-dashboard.html"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Start Python HTTP server
python3 -m http.server 8000
