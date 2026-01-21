#!/bin/bash
# VPS Update Script - Run on VPS
# Updates x0t-node container and sets up Nginx

set -euo pipefail

echo "🔄 Updating x0tta6bl4 on VPS..."

# Step 1: Stop old container
echo "Stopping old x0t-node container..."
docker stop x0t-node 2>/dev/null || echo "Container not running"

# Step 2: Load new image
echo "Loading new Docker image..."
docker load < /root/x0tta6bl4-app-staging.tar.gz
rm /root/x0tta6bl4-app-staging.tar.gz

# Step 3: Remove old container
echo "Removing old container..."
docker rm x0t-node 2>/dev/null || echo "Container already removed"

# Step 4: Stop simple http.server if running
echo "Stopping simple http.server on port 8080..."
pkill -f "python3 -m http.server 8080" 2>/dev/null || echo "http.server not running"

# Step 5: Start new container
echo "Starting new x0t-node container..."
docker run -d \
  --name x0t-node \
  --restart unless-stopped \
  -p 8081:8080 \
  -p 10809:10809 \
  -e NODE_ID=node-vps1 \
  -e ENVIRONMENT=production \
  -e LOG_LEVEL=INFO \
  x0tta6bl4-app:staging

# Step 6: Install Nginx if not installed
if ! command -v nginx &> /dev/null; then
    echo "Installing Nginx..."
    apt update
    apt install nginx -y
fi

# Step 7: Configure Nginx
echo "Configuring Nginx..."
cat > /etc/nginx/sites-available/x0tta6bl4 <<EOF
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://localhost:8081;
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
        proxy_pass http://localhost:8081/health;
        access_log off;
    }

    location /metrics {
        proxy_pass http://localhost:8081/metrics;
    }

    location /mesh/ {
        proxy_pass http://localhost:8081/mesh/;
    }
}
EOF

# Enable site
ln -sf /etc/nginx/sites-available/x0tta6bl4 /etc/nginx/sites-enabled/

# Remove default site if exists
rm -f /etc/nginx/sites-enabled/default

# Test and reload Nginx
nginx -t
systemctl reload nginx

# Step 8: Setup firewall (only if needed)
if command -v ufw &> /dev/null; then
    ufw allow 80/tcp 2>/dev/null || echo "Port 80 may already be open"
fi

echo ""
echo "✅ x0tta6bl4 update complete!"
echo ""
echo "📊 Service Status:"
echo "  - VPN (Xray): $(systemctl is-active xray 2>/dev/null || echo 'unknown')"
echo "  - x0t-node: $(docker ps --filter name=x0t-node --format '{{.Status}}')"
echo "  - Nginx: $(systemctl is-active nginx 2>/dev/null || echo 'unknown')"
echo ""
echo "🌐 Access URLs:"
echo "  - x0tta6bl4: http://$(hostname -I | awk '{print $1}')"
echo "  - Direct: http://localhost:8081"
echo "  - VPN: (unchanged, on original ports)"
echo ""
echo "📋 Useful commands:"
echo "  Check x0t-node: docker ps | grep x0t-node"
echo "  View logs: docker logs x0t-node -f"
echo "  Check VPN: systemctl status xray"
echo "  Restart x0t-node: docker restart x0t-node"

