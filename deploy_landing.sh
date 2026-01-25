#!/bin/bash
# Deployment script для Landing Page на VPS

set -e

echo "🌐 x0tta6bl4 Landing Page Deployment"
echo "====================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
VPS_HOST="${VPS_HOST:-89.125.1.107}"
VPS_USER="${VPS_USER:-root}"
LANDING_FILE="deployment/landing_simple.html"
REMOTE_PATH="/var/www/html/landing.html"

# Check if landing file exists
if [ ! -f "$LANDING_FILE" ]; then
    echo -e "${RED}✗${NC} Landing file not found: $LANDING_FILE"
    exit 1
fi

echo -e "${GREEN}✓${NC} Landing file found: $LANDING_FILE"

# Check if we can connect to VPS
echo ""
echo "🔌 Checking VPS connection..."
if ssh -o ConnectTimeout=5 "$VPS_USER@$VPS_HOST" "echo 'Connected'" 2>/dev/null; then
    echo -e "${GREEN}✓${NC} VPS connection OK"
else
    echo -e "${RED}✗${NC} Cannot connect to VPS"
    echo "Make sure:"
    echo "  1. SSH key is set up"
    echo "  2. VPS_HOST is correct (current: $VPS_HOST)"
    echo "  3. VPS_USER is correct (current: $VPS_USER)"
    exit 1
fi

# Upload landing page
echo ""
echo "📤 Uploading landing page..."
scp "$LANDING_FILE" "$VPS_USER@$VPS_HOST:$REMOTE_PATH"
echo -e "${GREEN}✓${NC} Landing page uploaded"

# Check nginx
echo ""
echo "🔍 Checking nginx..."
if ssh "$VPS_USER@$VPS_HOST" "command -v nginx &> /dev/null"; then
    echo -e "${GREEN}✓${NC} Nginx is installed"
    
    # Create nginx config if needed
    NGINX_CONFIG="/etc/nginx/sites-available/x0tta6bl4"
    
    ssh "$VPS_USER@$VPS_HOST" <<EOF
if [ ! -f "$NGINX_CONFIG" ]; then
    cat > "$NGINX_CONFIG" <<'NGINX_EOF'
server {
    listen 80;
    server_name $VPS_HOST;
    
    root /var/www/html;
    index landing.html;
    
    location / {
        try_files \$uri \$uri/ =404;
    }
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
}
NGINX_EOF
    echo "✓ Nginx config created"
    
    # Enable site
    if [ ! -L /etc/nginx/sites-enabled/x0tta6bl4 ]; then
        ln -s "$NGINX_CONFIG" /etc/nginx/sites-enabled/x0tta6bl4
        echo "✓ Site enabled"
    fi
    
    # Test and reload
    nginx -t && systemctl reload nginx
    echo "✓ Nginx reloaded"
else
    echo "✓ Nginx config already exists"
fi
EOF
    
    echo -e "${GREEN}✓${NC} Nginx configured"
else
    echo -e "${YELLOW}⚠${NC} Nginx not found, using simple HTTP server"
    echo "You can serve landing page with: python3 -m http.server 80"
fi

# Test accessibility
echo ""
echo "🧪 Testing accessibility..."
if curl -s -o /dev/null -w "%{http_code}" "http://$VPS_HOST/landing.html" | grep -q "200"; then
    echo -e "${GREEN}✓${NC} Landing page is accessible!"
    echo ""
    echo "🌐 URL: http://$VPS_HOST/landing.html"
else
    echo -e "${YELLOW}⚠${NC} Landing page may not be accessible yet"
    echo "Check nginx/service status on VPS"
fi

echo ""
echo -e "${GREEN}✅ Deployment complete!${NC}"

