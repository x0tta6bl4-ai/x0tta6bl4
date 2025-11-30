#!/bin/bash
# Deployment script для x0tta6bl4 Telegram Bot

set -e

echo "🚀 x0tta6bl4 Bot Deployment Script"
echo "===================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Please run as root${NC}"
    exit 1
fi

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo -e "${GREEN}✓${NC} Working directory: $SCRIPT_DIR"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗${NC} Python3 not found. Please install Python 3.8+"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo -e "${GREEN}✓${NC} Python version: $PYTHON_VERSION"

# Install dependencies
echo ""
echo "📦 Installing dependencies..."
if [ -f "requirements_bot.txt" ]; then
    pip3 install -r requirements_bot.txt
    echo -e "${GREEN}✓${NC} Dependencies installed"
else
    echo -e "${YELLOW}⚠${NC} requirements_bot.txt not found, installing aiogram only"
    pip3 install aiogram==2.25.1
fi

# Initialize database
echo ""
echo "🗄️  Initializing database..."
python3 -c "from database import init_database; init_database()" 2>/dev/null || {
    echo -e "${YELLOW}⚠${NC} Database initialization skipped (may already exist)"
}

# Check for bot token
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo ""
    echo -e "${YELLOW}⚠${NC} TELEGRAM_BOT_TOKEN not set"
    echo "Get token from @BotFather:"
    echo "1. Open Telegram"
    echo "2. Message @BotFather"
    echo "3. /newbot"
    echo "4. Follow instructions"
    echo ""
    read -p "Enter bot token (or press Enter to skip): " BOT_TOKEN
    if [ ! -z "$BOT_TOKEN" ]; then
        export TELEGRAM_BOT_TOKEN="$BOT_TOKEN"
        echo -e "${GREEN}✓${NC} Token set"
    else
        echo -e "${RED}✗${NC} Token required. Set TELEGRAM_BOT_TOKEN environment variable"
        exit 1
    fi
else
    echo -e "${GREEN}✓${NC} Bot token found"
fi

# Create systemd service
echo ""
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
Environment="TELEGRAM_PAYMENT_TOKEN=${TELEGRAM_PAYMENT_TOKEN:-}"
Environment="ADMIN_USER_ID=${ADMIN_USER_ID:-0}"
ExecStart=/usr/bin/python3 $SCRIPT_DIR/telegram_bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo -e "${GREEN}✓${NC} Service file created: $SERVICE_FILE"

# Reload systemd
systemctl daemon-reload
echo -e "${GREEN}✓${NC} Systemd reloaded"

# Enable service
systemctl enable x0tta6bl4-bot
echo -e "${GREEN}✓${NC} Service enabled"

# Start service
echo ""
echo "🔄 Starting bot service..."
systemctl restart x0tta6bl4-bot
sleep 2

# Check status
if systemctl is-active --quiet x0tta6bl4-bot; then
    echo -e "${GREEN}✓${NC} Bot is running!"
    echo ""
    echo "📊 Service status:"
    systemctl status x0tta6bl4-bot --no-pager -l
    echo ""
    echo "📝 View logs: journalctl -u x0tta6bl4-bot -f"
else
    echo -e "${RED}✗${NC} Bot failed to start"
    echo "Check logs: journalctl -u x0tta6bl4-bot -n 50"
    exit 1
fi

echo ""
echo -e "${GREEN}✅ Deployment complete!${NC}"
echo ""
echo "Useful commands:"
echo "  Start:   systemctl start x0tta6bl4-bot"
echo "  Stop:    systemctl stop x0tta6bl4-bot"
echo "  Restart: systemctl restart x0tta6bl4-bot"
echo "  Status:  systemctl status x0tta6bl4-bot"
echo "  Logs:    journalctl -u x0tta6bl4-bot -f"

