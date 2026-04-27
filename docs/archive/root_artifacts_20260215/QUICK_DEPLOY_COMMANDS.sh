#!/bin/bash
# Команды для быстрого деплоя - скопируй и выполни на VPS

export TELEGRAM_BOT_TOKEN="<REDACTED_TELEGRAM_BOT_TOKEN_ROTATE_ME>"

echo "🚀 x0tta6bl4 Bot Deployment"
echo "============================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "⚠️  Please run as root or with sudo"
    exit 1
fi

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "📁 Working directory: $SCRIPT_DIR"
echo ""

# Install dependencies
echo "📦 Installing dependencies..."
pip3 install aiogram==2.25.1 qrcode[pil]==7.4.2 2>/dev/null || {
    pip3 install --break-system-packages aiogram==2.25.1 qrcode[pil]==7.4.2
}
echo "✅ Dependencies installed"
echo ""

# Initialize database
echo "🗄️  Initializing database..."
python3 -c "from database import init_database; init_database()" 2>/dev/null || {
    echo "⚠️  Database may already exist"
}
echo "✅ Database ready"
echo ""

# Create systemd service
echo "⚙️  Creating systemd service..."
SERVICE_FILE="/etc/systemd/system/x0tta6bl4-bot.service"

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=x0tta6bl4 Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$SCRIPT_DIR
Environment="TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN"
ExecStart=/usr/bin/python3 $SCRIPT_DIR/telegram_bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo "✅ Service file created: $SERVICE_FILE"
echo ""

# Reload systemd
systemctl daemon-reload
echo "✅ Systemd reloaded"
echo ""

# Enable and start service
systemctl enable x0tta6bl4-bot
systemctl restart x0tta6bl4-bot
sleep 2

# Check status
if systemctl is-active --quiet x0tta6bl4-bot; then
    echo "✅ Bot is running!"
    echo ""
    echo "📊 Service status:"
    systemctl status x0tta6bl4-bot --no-pager -l | head -15
    echo ""
    echo "📝 View logs: journalctl -u x0tta6bl4-bot -f"
    echo ""
    echo "✅ Deployment complete!"
else
    echo "❌ Bot failed to start"
    echo "Check logs: journalctl -u x0tta6bl4-bot -n 50"
    exit 1
fi

