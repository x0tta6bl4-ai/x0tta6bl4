#!/bin/bash
# Quick deployment script

set -euo pipefail

: "${TELEGRAM_BOT_TOKEN:?Set TELEGRAM_BOT_TOKEN in environment}"

echo "🚀 Quick Deployment Script"
echo "=========================="
echo ""
echo "This will:"
echo "1. Deploy bot to VPS (89.125.1.107)"
echo "2. Deploy landing page"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
fi

echo ""
echo "📤 Deploying bot..."
cd /mnt/AC74CC2974CBF3DC

# Check if we're on VPS or local
if [ "$(hostname)" = "89.125.1.107" ] || [ -f "/root/.ssh/id_rsa" ]; then
    # On VPS or have SSH access
    echo "Running deploy_bot.sh on VPS..."
    sudo TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN" ./deploy_bot.sh
else
    echo "⚠️  Need to deploy via SSH to VPS"
    echo "Run on VPS:"
    echo "  export TELEGRAM_BOT_TOKEN='<your_token>'"
    echo "  sudo ./deploy_bot.sh"
fi

echo ""
echo "🌐 Deploying landing page..."
./deploy_landing.sh

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Check bot status:"
echo "  ssh root@89.125.1.107 'systemctl status x0tta6bl4-bot'"
echo ""
echo "View bot logs:"
echo "  ssh root@89.125.1.107 'journalctl -u x0tta6bl4-bot -f'"
