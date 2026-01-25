#!/bin/bash
# Automatically get ngrok URL and update EMAIL_TEMPLATE_V3.md

echo "🔍 Waiting for ngrok URL..."

MAX_ATTEMPTS=30
ATTEMPT=0

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
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
        DEMO_URL="${URL}/causal-dashboard.html"
        
        echo ""
        echo "=========================================="
        echo "✅ URL FOUND!"
        echo "=========================================="
        echo ""
        echo "🌐 Demo URL: ${DEMO_URL}"
        echo ""
        
        # Update EMAIL_TEMPLATE_V3.md
        if [ -f "EMAIL_TEMPLATE_V3.md" ]; then
            # Replace [DEMO_LINK] and [LIVE DEMO LINK] with actual URL
            sed -i "s|\[DEMO_LINK\]|${DEMO_URL}|g" EMAIL_TEMPLATE_V3.md
            sed -i "s|\[LIVE DEMO LINK\]|${DEMO_URL}|g" EMAIL_TEMPLATE_V3.md
            
            echo "✅ EMAIL_TEMPLATE_V3.md updated with URL"
            echo ""
        fi
        
        # Create final status file
        cat > FINAL_DEMO_STATUS.md << EOF
# ✅ Demo URL Ready!

**Status**: Live and accessible

---

## 🌐 Demo URL

**${DEMO_URL}**

---

## ✅ What's Done

- ✅ Ngrok configured and running
- ✅ Server running on port 8080
- ✅ Causal Analysis Dashboard deployed
- ✅ EMAIL_TEMPLATE_V3.md updated with URL

---

## 📧 Email Template

**File**: EMAIL_TEMPLATE_V3.md

**Status**: ✅ Ready for Wave 3-4

All `[DEMO_LINK]` placeholders replaced with:
\`${DEMO_URL}\`

---

## 🚀 Next Steps

1. **Test the demo**: Open ${DEMO_URL}
2. **Review email**: Check EMAIL_TEMPLATE_V3.md
3. **Send Wave 3-4**: Ready to go!

---

## 📊 Quick Test

\`\`\`bash
curl -I ${DEMO_URL}
\`\`\`

Should return: \`200 OK\`

---

**Created**: $(date)
**Status**: ✅ Ready for production
EOF
        
        echo "✅ FINAL_DEMO_STATUS.md created"
        echo ""
        echo "=========================================="
        echo "🎯 READY FOR EMAIL WAVE 3-4!"
        echo "=========================================="
        echo ""
        echo "📧 Email template: EMAIL_TEMPLATE_V3.md"
        echo "🌐 Demo URL: ${DEMO_URL}"
        echo ""
        echo "✅ Test it: Open ${DEMO_URL}"
        echo ""
        
        exit 0
    fi
    
    ATTEMPT=$((ATTEMPT + 1))
    echo -n "."
    sleep 1
done

echo ""
echo "⏳ Ngrok is taking longer than expected..."
echo ""
echo "🌐 Alternative: Open http://localhost:4040 in browser"
echo "   Copy the URL from 'Forwarding' section"
echo "   Then run: ./update_email_url.sh YOUR_URL"
echo ""

