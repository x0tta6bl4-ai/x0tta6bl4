#!/bin/bash
# VPS Setup Script - Run on VPS
# Sets up Docker, loads image, configures Nginx

set -euo pipefail

DOMAIN="${1:-}"

echo "🚀 Setting up x0tta6bl4 on VPS..."

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
mkdir -p /root/data

# Step 5: Start Docker Compose
echo "Starting application..."
cd /root
docker-compose up -d

# Step 6: Setup Nginx (if not installed)
if ! command -v nginx &> /dev/null; then
    echo "Installing Nginx..."
    apt update
    apt install nginx -y
fi

# Step 7: Configure Nginx
SERVER_NAME="${DOMAIN:-_}"
cat > /etc/nginx/sites-available/x0tta6bl4 <<EOF
server {
    listen 80;
    server_name $SERVER_NAME;

    location / {
        proxy_pass http://localhost:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
    }

    location /health {
        proxy_pass http://localhost:8080/health;
        access_log off;
    }

    location /metrics {
        proxy_pass http://localhost:8080/metrics;
    }
}
EOF

# Enable site
ln -sf /etc/nginx/sites-available/x0tta6bl4 /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test and reload Nginx
nginx -t
systemctl reload nginx

# Step 8: Setup firewall
if command -v ufw &> /dev/null; then
    ufw allow 22/tcp
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw allow 8080/tcp
    ufw --force enable || true
fi

# Step 9: SSL (if domain provided)
if [ -n "$DOMAIN" ]; then
    if command -v certbot &> /dev/null || apt install certbot python3-certbot-nginx -y; then
        echo "Setting up SSL for $DOMAIN..."
        certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN || echo "SSL setup skipped (may need manual setup)"
    fi
fi

echo "✅ VPS setup complete!"
echo ""
echo "Application is running on:"
echo "  - Direct: http://localhost:8080"
echo "  - Nginx: http://${DOMAIN:-$(hostname -I | awk '{print $1}')}"
echo ""
echo "Check status: docker ps"
echo "View logs: docker logs x0tta6bl4-production -f"

