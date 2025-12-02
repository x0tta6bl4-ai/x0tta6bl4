#!/bin/bash
set -e

echo "🚀 Starting X0T Production Deployment..."

# 1. Install Smart Contract Dependencies
echo "📦 Installing contract dependencies..."
cd src/dao/contracts
if [ ! -d "node_modules" ]; then
    npm install
fi
cd ../../../

# 2. Check Configuration
if [ ! -f "src/dao/contracts/.env" ]; then
    echo "⚠️  .env file missing in src/dao/contracts/"
    echo "   Please copy .env.example and fill in PRIVATE_KEY"
    cp src/dao/contracts/.env.example src/dao/contracts/.env
    exit 1
fi

# 3. Ask for Deploy Target
echo ""
echo "Select deployment target:"
echo "1) Base Sepolia (Testnet)"
echo "2) Polygon Mainnet"
echo "3) Local Hardhat Node"
read -p "Choice [1-3]: " choice

case $choice in
    1)
        CMD="npm run deploy:base-testnet"
        ;;
    2)
        CMD="npm run deploy:polygon"
        ;;
    3)
        CMD="npm run deploy:local"
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

# 4. Deploy Contract
echo "⛓️  Deploying contract..."
cd src/dao/contracts
$CMD
cd ../../../

# 5. Setup Scheduler Service
echo "⚙️  Setting up Epoch Scheduler Service..."
if [ -d "/etc/systemd/system" ]; then
    sudo cp infra/systemd/x0t-scheduler.service /etc/systemd/system/
    sudo systemctl daemon-reload
    # sudo systemctl enable x0t-scheduler
    # sudo systemctl start x0t-scheduler
    echo "✅ Service installed (start manually with 'sudo systemctl start x0t-scheduler')"
else
    echo "⚠️  Systemd not found, skipping service install"
fi

echo ""
echo "🎉 Deployment Setup Complete!"
echo "   To start scheduler: python3 src/dao/run_scheduler.py"
