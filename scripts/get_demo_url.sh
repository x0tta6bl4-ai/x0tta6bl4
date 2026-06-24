#!/bin/bash
# Get ngrok demo URL automatically

echo "🔍 Checking ngrok status..."

for i in {1..15}; do
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
        echo "📧 Use in EMAIL_TEMPLATE_V3.md:"
        echo "   [DEMO_LINK] → ${URL}/causal-dashboard.html"
        echo ""
        echo "✅ Test: Open ${URL}/causal-dashboard.html"
        echo ""
        echo "=========================================="
        echo ""
        exit 0
    fi
    
    echo -n "."
    sleep 1
done

echo ""
echo "⏳ Ngrok is still starting..."
echo ""
echo "🌐 Alternative: Open http://localhost:4040 in browser"
echo "   The URL will be visible in the 'Forwarding' section"
echo ""

