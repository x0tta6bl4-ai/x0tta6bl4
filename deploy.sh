#!/bin/bash
# ═══════════════════════════════════════════════════════════════
#  Deployment Script for Digital Survival Kit Sales Bot
# ═══════════════════════════════════════════════════════════════

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}🚀 x0tta6bl4 Digital Survival Kit - Deployment Script${NC}"
echo ""

# Check for root privileges
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}❌ This script must be run as root${NC}"
  exit 1
fi

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 not found${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Python found: $(python3 --version)${NC}"

# Install dependencies
echo ""
echo -e "${YELLOW}📦 Installing dependencies...${NC}"
pip3 install -q -r requirements.txt || {
    echo -e "${RED}❌ Failed to install dependencies${NC}"
    exit 1
}

echo -e "${GREEN}✅ Dependencies installed${NC}"

# Create .env file
if [ ! -f ".env" ]; then
    echo ""
    echo -e "${YELLOW}⚠️  .env file not found${NC}"
    echo "Creating .env..."
    
    read -p "Enter your TELEGRAM_BOT_TOKEN: " TELEGRAM_BOT_TOKEN
    read -p "Enter your USDT_TRC20_WALLET: " USDT_TRC20_WALLET
    read -p "Enter your TON_WALLET: " TON_WALLET
    read -p "Enter your ADMIN_USER_IDS (comma-separated): " ADMIN_USER_IDS

    cat > .env <<EOF
TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
USDT_TRC20_WALLET=${USDT_TRC20_WALLET}
TON_WALLET=${TON_WALLET}
ADMIN_USER_IDS=${ADMIN_USER_IDS}
EOF
    echo -e "${GREEN}✅ Created .env file${NC}"
else
    echo -e "${GREEN}✅ .env file already exists${NC}"
fi

# Initialize database
echo ""
echo -e "${YELLOW}📦 Initializing database...${NC}"
python3 -c "from database import init_database; init_database()" || {
    echo -e "${RED}❌ Failed to initialize database${NC}"
    exit 1
}
echo -e "${GREEN}✅ Database initialized${NC}"

# Create systemd service
echo ""
echo -e "${YELLOW}📦 Creating systemd service...${NC}"
cat > /etc/systemd/system/x0tta6bl4-bot.service <<EOF
[Unit]
Description=x0tta6bl4 Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$(pwd)
EnvironmentFile=$(pwd)/.env
ExecStart=/usr/bin/python3 $(pwd)/telegram_bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
echo -e "${GREEN}✅ Systemd service created${NC}"

# Start service
echo ""
echo -e "${YELLOW}🚀 Starting service...${NC}"
systemctl daemon-reload
systemctl enable x0tta6bl4-bot
systemctl start x0tta6bl4-bot
echo -e "${GREEN}✅ Service started${NC}"

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ DEPLOYMENT COMPLETE!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${YELLOW}Next steps:${NC}"
echo ""
echo "  1. Check the bot status:"
echo "     ${GREEN}systemctl status x0tta6bl4-bot${NC}"
echo ""
echo "  2. Check the logs:"
echo "     ${GREEN}journalctl -u x0tta6bl4-bot -f${NC}"
echo ""
echo "  3. Test in Telegram:"
echo "     - Find your bot"
echo "     - Send /start"
echo "     - Check if it responds"
echo ""
echo -e "${GREEN}  Ready to sell! 🚀${NC}"
echo ""