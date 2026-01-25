#!/bin/bash
# Start server and ngrok together

echo "Starting demo server on port 8080..."
cd /mnt/AC74CC2974CBF3DC/web/demo
python3 -m http.server 8080 &
SERVER_PID=$!

sleep 2

echo "✅ Server started (PID: $SERVER_PID)"
echo ""
echo "Starting ngrok..."
echo ""

ngrok http 8080

# Cleanup on exit
trap "kill $SERVER_PID 2>/dev/null; exit" INT TERM
