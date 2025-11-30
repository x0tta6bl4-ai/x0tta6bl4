#!/bin/bash
# Quick Ngrok Setup - 5 минут до live demo
# Работает через VPN, не требует VPS

set -e

echo "=========================================="
echo "🚀 Ngrok Quick Setup (5 минут)"
echo "=========================================="
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 not found. Please install Python 3.8+"
    exit 1
fi

# Check if ngrok is installed
if ! command -v ngrok &> /dev/null; then
    echo "📦 Installing ngrok..."
    
    # Detect architecture
    ARCH=$(uname -m)
    if [ "$ARCH" = "x86_64" ]; then
        NGROK_ARCH="amd64"
    elif [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
        NGROK_ARCH="arm64"
    else
        echo "❌ Unsupported architecture: $ARCH"
        exit 1
    fi
    
    # Download ngrok
    NGROK_URL="https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-${NGROK_ARCH}.tgz"
    
    echo "Downloading ngrok..."
    curl -L "$NGROK_URL" -o /tmp/ngrok.tgz || {
        echo "❌ Failed to download ngrok. Try manual install:"
        echo "   Visit: https://ngrok.com/download"
        exit 1
    }
    
    # Extract
    tar -xzf /tmp/ngrok.tgz -C /tmp/
    
    # Install
    if [ -w /usr/local/bin ]; then
        sudo mv /tmp/ngrok /usr/local/bin/
    else
        mkdir -p ~/.local/bin
        mv /tmp/ngrok ~/.local/bin/
        export PATH="$HOME/.local/bin:$PATH"
        echo "✅ ngrok installed to ~/.local/bin (add to PATH)"
    fi
    
    rm /tmp/ngrok.tgz
    echo "✅ ngrok installed"
else
    echo "✅ ngrok already installed"
fi

# Check authentication
if [ ! -f ~/.ngrok2/ngrok.yml ] && [ ! -f ~/.config/ngrok/ngrok.yml ]; then
    echo ""
    echo "🔐 Ngrok authentication required"
    echo ""
    echo "1. Open: https://dashboard.ngrok.com/signup"
    echo "2. Sign up (free, takes 30 seconds)"
    echo "3. Get authtoken from: https://dashboard.ngrok.com/get-started/your-authtoken"
    echo ""
    read -p "Enter your ngrok authtoken: " AUTHTOKEN
    
    if [ -z "$AUTHTOKEN" ]; then
        echo "❌ Authtoken required. Exiting."
        exit 1
    fi
    
    ngrok config add-authtoken "$AUTHTOKEN" || {
        echo "❌ Failed to add authtoken. Check your token."
        exit 1
    }
    
    echo "✅ ngrok authenticated"
else
    echo "✅ ngrok already authenticated"
fi

# Get project directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo ""
echo "📦 Starting x0tta6bl4 server..."

# Check if server is already running
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "⚠️  Port 8000 already in use. Stopping existing process..."
    pkill -f "src.core.app" || true
    sleep 2
fi

# Start server in background
cd "$PROJECT_ROOT"
python3 -m src.core.app > /tmp/x0tta6bl4-server.log 2>&1 &
SERVER_PID=$!

# Wait for server
echo "Waiting for server to start..."
for i in {1..10}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ Server started (PID: $SERVER_PID)"
        break
    fi
    sleep 1
    if [ $i -eq 10 ]; then
        echo "❌ Server failed to start. Check logs: /tmp/x0tta6bl4-server.log"
        kill $SERVER_PID 2>/dev/null || true
        exit 1
    fi
done

echo ""
echo "🌐 Starting ngrok tunnel..."

# Start ngrok
ngrok http 8000 > /tmp/ngrok.log 2>&1 &
NGROK_PID=$!

# Wait for ngrok
sleep 5

# Get public URL
NGROK_URL=""
for i in {1..10}; do
    NGROK_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | grep -o '"public_url":"https://[^"]*' | head -1 | cut -d'"' -f4)
    if [ -n "$NGROK_URL" ]; then
        break
    fi
    sleep 1
done

if [ -z "$NGROK_URL" ]; then
    echo "❌ Failed to get ngrok URL"
    echo "Check ngrok logs: /tmp/ngrok.log"
    kill $SERVER_PID $NGROK_PID 2>/dev/null || true
    exit 1
fi

DEMO_URL="${NGROK_URL}/demo/causal-dashboard.html"

echo ""
echo "=========================================="
echo "✅ DEMO IS LIVE!"
echo "=========================================="
echo ""
echo "🌐 Demo URL: $DEMO_URL"
echo ""
echo "📋 Test it now:"
echo "   1. Open: $DEMO_URL"
echo "   2. Click '🚀 Load Demo Incident'"
echo "   3. Verify animations work"
echo ""
echo "📧 Use this URL in your email:"
echo "   $DEMO_URL"
echo ""
echo "📊 Ngrok Dashboard:"
echo "   http://localhost:4040 (local monitoring)"
echo ""
echo "⚠️  Important:"
echo "   - Keep this terminal open (closing stops tunnel)"
echo "   - URL valid for 24 hours (free tier)"
echo "   - For production, use VPS deployment later"
echo ""
echo "🛑 To stop: Press Ctrl+C"
echo ""

# Save URL to file
echo "$DEMO_URL" > /tmp/x0tta6bl4-demo-url.txt
echo "✅ URL saved to: /tmp/x0tta6bl4-demo-url.txt"

# Keep script running
trap "echo ''; echo '🛑 Stopping...'; kill $SERVER_PID $NGROK_PID 2>/dev/null; exit" INT TERM

echo "Press Ctrl+C to stop..."
wait

