#!/bin/bash
# ═══════════════════════════════════════════════════════════════
#  Quick Setup Script for Digital Survival Kit Sales Bot
# ═══════════════════════════════════════════════════════════════

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}🚀 x0tta6bl4 Digital Survival Kit - Quick Setup${NC}"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 not found${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Python found: $(python3 --version)${NC}"

# Install dependencies
echo ""
echo -e "${YELLOW}📦 Installing dependencies...${NC}"
pip install -q python-telegram-bot cryptography requests python-dotenv || {
    echo -e "${RED}❌ Failed to install dependencies${NC}"
    exit 1
}

echo -e "${GREEN}✅ Dependencies installed${NC}"

# Check .env file
if [ ! -f ".env" ]; then
    echo ""
    echo -e "${YELLOW}⚠️  .env file not found${NC}"
    echo "Creating .env.example..."
    
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "${GREEN}✅ Created .env from .env.example${NC}"
        echo ""
        echo -e "${YELLOW}⚠️  IMPORTANT: Edit .env and add your:${NC}"
        echo "   - TELEGRAM_BOT_TOKEN"
        echo "   - USDT_TRC20_WALLET"
        echo "   - TON_WALLET"
        echo ""
        read -p "Press Enter after editing .env..."
    else
        echo -e "${RED}❌ .env.example not found${NC}"
        exit 1
    fi
fi

# Check if token is set
if grep -q "YOUR_BOT_TOKEN_HERE" .env || grep -q "your_bot_token" .env; then
    echo -e "${RED}❌ TELEGRAM_BOT_TOKEN not configured in .env${NC}"
    echo "   Please edit .env and add your bot token"
    exit 1
fi

# Test license system
echo ""
echo -e "${YELLOW}🧪 Testing license system...${NC}"
python3 -c "from src.licensing.node_identity import HardwareFingerprinter; fp = HardwareFingerprinter.generate(); print('✅ License system OK')" || {
    echo -e "${RED}❌ License system test failed${NC}"
    exit 1
}

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ SETUP COMPLETE!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${YELLOW}Next steps:${NC}"
echo ""
echo "  1. Start the bot:"
echo "     ${GREEN}python3 src/sales/telegram_bot.py${NC}"
echo ""
echo "  2. Test in Telegram:"
echo "     - Find your bot"
echo "     - Send /start"
echo "     - Check if it responds"
echo ""
echo "  3. For production, use systemd:"
echo "     See SETUP_GUIDE.md"
echo ""
echo -e "${GREEN}  Ready to sell! 🚀${NC}"
echo ""

