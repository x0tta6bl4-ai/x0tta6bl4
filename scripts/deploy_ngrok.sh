#!/bin/bash
# Ngrok Deployment Script for Quick Demo
# Creates temporary public URL for testing

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=========================================="
echo "Ngrok Quick Demo Deployment"
echo "=========================================="
echo ""
echo "⚠️  Note: This creates a temporary public URL (24 hours free tier)"
echo "   For production email, use VPS deployment instead"
echo ""

# Check if ngrok is installed
if ! command -v ngrok &> /dev/null; then
    echo "📦 Installing ngrok..."
    
    # Detect OS
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        NGROK_URL="https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz"
        curl -L "$NGROK_URL" -o /tmp/ngrok.tgz
        tar -xzf /tmp/ngrok.tgz -C /tmp/
        sudo mv /tmp/ngrok /usr/local/bin/
        rm /tmp/ngrok.tgz
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        brew install ngrok/ngrok/ngrok || {
            echo "Please install ngrok manually: https://ngrok.com/download"
            exit 1
        }
    else
        echo "Please install ngrok manually: https://ngrok.com/download"
        exit 1
    fi
    
    echo "✅ ngrok installed"
fi

# Check if ngrok is authenticated
if [ ! -f ~/.ngrok2/ngrok.yml ] && [ ! -f ~/.config/ngrok/ngrok.yml ]; then
    echo ""
    echo "🔐 Ngrok authentication required"
    echo "1. Sign up at https://dashboard.ngrok.com/signup"
    echo "2. Get your authtoken from https://dashboard.ngrok.com/get-started/your-authtoken"
    read -p "Enter your ngrok authtoken: " AUTHTOKEN
    ngrok config add-authtoken "$AUTHTOKEN"
    echo "✅ ngrok authenticated"
fi

echo ""
echo "🚀 Starting x0tta6bl4 server..."

# Start server in background
cd "$PROJECT_ROOT"
python -m src.core.app &
SERVER_PID=$!

# Wait for server to start
sleep 3

# Check if server is running
if ! kill -0 $SERVER_PID 2>/dev/null; then
    echo "❌ Server failed to start"
    exit 1
fi

echo "✅ Server started (PID: $SERVER_PID)"

echo ""
echo "🌐 Starting ngrok tunnel..."

# Start ngrok
ngrok http 8000 > /tmp/ngrok.log 2>&1 &
NGROK_PID=$!

# Wait for ngrok to start
sleep 3

# Get public URL
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o '"public_url":"https://[^"]*' | cut -d'"' -f4)

if [ -z "$NGROK_URL" ]; then
    echo "❌ Failed to get ngrok URL"
    kill $SERVER_PID $NGROK_PID 2>/dev/null || true
    exit 1
fi

echo ""
echo "=========================================="
echo "✅ Demo is live!"
echo "=========================================="
echo ""
echo "🌐 Public URL: $NGROK_URL/demo/causal-dashboard.html"
echo ""
echo "📋 Test it:"
echo "  1. Open: $NGROK_URL/demo/causal-dashboard.html"
echo "  2. Click 'Load Demo Incident'"
echo "  3. Verify animations work"
echo ""
echo "📧 Use this URL in your email:"
echo "   $NGROK_URL/demo/causal-dashboard.html"
echo ""
echo "⚠️  Important:"
echo "  - This URL is temporary (24 hours on free tier)"
echo "  - Keep this terminal open (closing stops the tunnel)"
echo "  - For production, use VPS deployment"
echo ""
echo "🛑 To stop: Press Ctrl+C or run:"
echo "   kill $SERVER_PID $NGROK_PID"
echo ""

# Keep script running
trap "kill $SERVER_PID $NGROK_PID 2>/dev/null; exit" INT TERM
wait

