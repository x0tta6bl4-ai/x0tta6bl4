#!/bin/bash
# Get ngrok URL from API

echo "Checking ngrok status..."

# Wait for ngrok API
for i in {1..10}; do
    URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    tunnels = data.get('tunnels', [])
    if tunnels and tunnels[0].get('public_url'):
        print(tunnels[0]['public_url'])
except:
    pass
" 2>/dev/null)
    
    if [ -n "$URL" ]; then
        echo ""
        echo "=========================================="
        echo "✅ LIVE DEMO URL READY!"
        echo "=========================================="
        echo ""
        echo "🌐 Demo URL: ${URL}/causal-dashboard.html"
        echo ""
        echo "📧 Use this in EMAIL_TEMPLATE_V3.md:"
        echo "   [DEMO_LINK] → ${URL}/causal-dashboard.html"
        echo ""
        echo "✅ Test it: Open ${URL}/causal-dashboard.html"
        echo ""
        exit 0
    fi
    
    sleep 1
done

echo "⏳ Ngrok is starting... Please wait a few more seconds"
echo "   Then run this script again: ./GET_NGROK_URL.sh"

