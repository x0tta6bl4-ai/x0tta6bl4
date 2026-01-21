#!/bin/bash
# VPS Setup Script with existing VPN - Run on VPS
# Sets up x0tta6bl4 without interfering with VPN

set -euo pipefail

DOMAIN="${1:-}"
APP_PORT="${2:-8080}"

echo "🚀 Setting up x0tta6bl4 on VPS (preserving VPN)..."

# Check if VPN is running
if systemctl is-active --quiet xray || pgrep -x xray > /dev/null; then
    echo "✅ VPN (Xray) is running - will preserve it"
else
    echo "⚠️  VPN not detected, but continuing anyway"
fi

# Step 1: Install Docker (if not installed)
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
fi

# Step 2: Install Docker Compose (if not installed)
if ! command -v docker-compose &> /dev/null; then
    echo "Installing Docker Compose..."
    apt update
    apt install docker-compose -y
fi

# Step 3: Load Docker image
echo "Loading Docker image..."
docker load < /root/x0tta6bl4-app-staging.tar.gz
rm /root/x0tta6bl4-app-staging.tar.gz

# Step 4: Create data directory
mkdir -p /root/x0tta6bl4-data

# Step 5: Start Docker Compose (using different compose file name)
echo "Starting x0tta6bl4 application..."
cd /root
docker-compose -f docker-compose-x0tta6bl4.yml up -d

# Step 6: Setup Nginx (if not installed)
if ! command -v nginx &> /dev/null; then
    echo "Installing Nginx..."
    apt update
    apt install nginx -y
fi

# Step 7: Configure Nginx for x0tta6bl4 (separate from VPN)
SERVER_NAME="${DOMAIN:-_}"
cat > /etc/nginx/sites-available/x0tta6bl4 <<EOF
# x0tta6bl4 Application (separate from VPN)
server {
    listen 80;
    server_name $SERVER_NAME;

    # x0tta6bl4 application
    location / {
        proxy_pass http://localhost:$APP_PORT;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
    }

    # Health check endpoint
    location /health {
        proxy_pass http://localhost:$APP_PORT/health;
        access_log off;
    }

    # Metrics endpoint
    location /metrics {
        proxy_pass http://localhost:$APP_PORT/metrics;
    }

    # Mesh endpoints
    location /mesh/ {
        proxy_pass http://localhost:$APP_PORT/mesh/;
    }
}
EOF

# Enable site (don't remove default if it's used by VPN panel)
ln -sf /etc/nginx/sites-available/x0tta6bl4 /etc/nginx/sites-enabled/

# Test and reload Nginx
nginx -t
systemctl reload nginx

# Step 8: Setup firewall (only if needed, don't break VPN)
if command -v ufw &> /dev/null; then
    # Check if ports are already open
    ufw allow $APP_PORT/tcp 2>/dev/null || echo "Port $APP_PORT may already be open"
    ufw allow 80/tcp 2>/dev/null || echo "Port 80 may already be open"
    ufw allow 443/tcp 2>/dev/null || echo "Port 443 may already be open"
fi

# Step 9: SSL (if domain provided and VPN doesn't use it)
if [ -n "$DOMAIN" ]; then
    # Check if SSL already exists for this domain
    if [ ! -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
        if command -v certbot &> /dev/null || apt install certbot python3-certbot-nginx -y; then
            echo "Setting up SSL for $DOMAIN..."
            certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN || echo "SSL setup skipped"
        fi
    else
        echo "SSL certificate already exists for $DOMAIN"
    fi
fi

echo ""
echo "✅ x0tta6bl4 setup complete!"
echo ""
echo "📊 Service Status:"
echo "  - VPN (Xray): $(systemctl is-active xray 2>/dev/null || echo 'unknown')"
echo "  - x0tta6bl4: $(docker ps --filter name=x0tta6bl4-production --format '{{.Status}}')"
echo ""
echo "🌐 Access URLs:"
echo "  - x0tta6bl4: http://${DOMAIN:-$(hostname -I | awk '{print $1}')}"
echo "  - Direct: http://localhost:$APP_PORT"
echo "  - VPN: (unchanged, on original ports)"
echo ""
echo "📋 Useful commands:"
echo "  Check x0tta6bl4: docker ps | grep x0tta6bl4"
echo "  View logs: docker logs x0tta6bl4-production -f"
echo "  Check VPN: systemctl status xray"
echo "  Restart x0tta6bl4: docker-compose -f docker-compose-x0tta6bl4.yml restart"

