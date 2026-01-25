#!/bin/bash
# VPS Deployment Script for Causal Analysis Demo
# Supports: DigitalOcean, Hetzner, AWS, any Ubuntu/Debian VPS

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=========================================="
echo "VPS Deployment: Causal Analysis Demo"
echo "=========================================="
echo ""

# Configuration
read -p "Enter VPS host (user@hostname or IP): " VPS_HOST
read -p "Enter deployment path (default: /opt/x0tta6bl4-demo): " DEPLOY_PATH
DEPLOY_PATH="${DEPLOY_PATH:-/opt/x0tta6bl4-demo}"

read -p "Enter domain name (e.g., demo.yourdomain.com) or press Enter to skip: " DOMAIN_NAME

echo ""
echo "📦 Step 1: Preparing deployment package..."

# Create deployment package
TEMP_DIR=$(mktemp -d)
cd "$PROJECT_ROOT"

# Copy necessary files
mkdir -p "$TEMP_DIR/deploy"
cp -r src "$TEMP_DIR/deploy/"
cp -r web "$TEMP_DIR/deploy/"
cp pyproject.toml "$TEMP_DIR/deploy/"
cp requirements.txt "$TEMP_DIR/deploy/" 2>/dev/null || echo "# Requirements" > "$TEMP_DIR/deploy/requirements.txt"

# Create deployment archive
cd "$TEMP_DIR"
tar -czf deploy.tar.gz deploy/
echo "✅ Deployment package created"

echo ""
echo "📤 Step 2: Uploading to VPS..."

# Upload to VPS
scp deploy.tar.gz "$VPS_HOST:/tmp/"
ssh "$VPS_HOST" "mkdir -p $DEPLOY_PATH && cd $DEPLOY_PATH && tar -xzf /tmp/deploy.tar.gz && mv deploy/* . && rm -rf deploy /tmp/deploy.tar.gz"

echo "✅ Files uploaded"

echo ""
echo "🔧 Step 3: Setting up on VPS..."

# Create setup script on VPS
ssh "$VPS_HOST" "cat > $DEPLOY_PATH/setup.sh <<'SETUP_EOF'
#!/bin/bash
set -e

# Install Python and dependencies
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install project
pip install --upgrade pip
pip install -e .

# Create systemd service
sudo tee /etc/systemd/system/x0tta6bl4-demo.service > /dev/null <<EOF
[Unit]
Description=x0tta6bl4 Causal Analysis Demo
After=network.target

[Service]
Type=simple
User=\$(whoami)
WorkingDirectory=$DEPLOY_PATH
Environment=\"PATH=$DEPLOY_PATH/venv/bin\"
ExecStart=$DEPLOY_PATH/venv/bin/python -m src.core.app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable x0tta6bl4-demo
sudo systemctl start x0tta6bl4-demo

echo '✅ Service started'
SETUP_EOF
chmod +x $DEPLOY_PATH/setup.sh"

# Run setup
ssh "$VPS_HOST" "cd $DEPLOY_PATH && ./setup.sh"

echo "✅ Application setup complete"

# Setup nginx if domain provided
if [ -n "$DOMAIN_NAME" ]; then
    echo ""
    echo "🌐 Step 4: Setting up Nginx and SSL..."
    
    ssh "$VPS_HOST" "sudo tee /etc/nginx/sites-available/x0tta6bl4-demo > /dev/null <<EOF
server {
    listen 80;
    server_name $DOMAIN_NAME;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
    sudo ln -sf /etc/nginx/sites-available/x0tta6bl4-demo /etc/nginx/sites-enabled/
    sudo nginx -t && sudo systemctl reload nginx
    
    echo '✅ Nginx configured'
    echo ''
    echo '🔒 Step 5: Setting up SSL certificate...'
    echo 'Run this command on VPS:'
    echo "sudo certbot --nginx -d $DOMAIN_NAME"
    echo ''
    echo 'Or run automatically (requires email):'
    read -p "Enter email for Let's Encrypt: " EMAIL
    ssh "$VPS_HOST" "sudo certbot --nginx -d $DOMAIN_NAME --non-interactive --agree-tos --email $EMAIL"
    
    echo "✅ SSL certificate installed"
    echo ""
    echo "🎉 Deployment complete!"
    echo "Demo available at: https://$DOMAIN_NAME/demo/causal-dashboard.html"
else
    echo ""
    echo "⚠️  No domain configured. Access via:"
    echo "http://$(echo $VPS_HOST | cut -d'@' -f2):8000/demo/causal-dashboard.html"
    echo ""
    echo "To add domain later, run:"
    echo "ssh $VPS_HOST 'sudo certbot --nginx -d your-domain.com'"
fi

# Cleanup
rm -rf "$TEMP_DIR"

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📋 Useful commands:"
echo "  Check status: ssh $VPS_HOST 'sudo systemctl status x0tta6bl4-demo'"
echo "  View logs: ssh $VPS_HOST 'sudo journalctl -u x0tta6bl4-demo -f'"
echo "  Restart: ssh $VPS_HOST 'sudo systemctl restart x0tta6bl4-demo'"

