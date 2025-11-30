#!/bin/bash
# Manually update email template with ngrok URL

if [ -z "$1" ]; then
    echo "Usage: $0 <ngrok-url>"
    echo "Example: $0 https://xxxxx.ngrok.io"
    exit 1
fi

URL="$1"
DEMO_URL="${URL}/causal-dashboard.html"

echo "Updating EMAIL_TEMPLATE_V3.md with: ${DEMO_URL}"

if [ -f "EMAIL_TEMPLATE_V3.md" ]; then
    sed -i "s|\[DEMO_LINK\]|${DEMO_URL}|g" EMAIL_TEMPLATE_V3.md
    sed -i "s|\[LIVE DEMO LINK\]|${DEMO_URL}|g" EMAIL_TEMPLATE_V3.md
    
    echo "✅ EMAIL_TEMPLATE_V3.md updated!"
    echo ""
    echo "Demo URL: ${DEMO_URL}"
else
    echo "❌ EMAIL_TEMPLATE_V3.md not found"
    exit 1
fi

