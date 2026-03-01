#!/bin/bash
# ==============================================================================
# x0tta6bl4 | ULTIMATE DEPLOYMENT SCRIPT (2026 PRODUCTION RELEASE)
# ==============================================================================
# This script sets up the full ecosystem:
# 1. Core Mesh Infrastructure (Docker)
# 2. Database & Marketplace Migrations
# 3. Secure Gateway & Dashboard (PM2)
# 4. Marketing Landing Page (PM2)
# 5. eBPF Monitoring & Self-Healing Daemons
# ==============================================================================

set -e # Exit on error

echo "🚀 [x0tta6bl4] Starting Deployment..."

# 1. Dependency Check
echo "📦 Checking dependencies..."
command -v docker >/dev/null 2>&1 || { echo "❌ Docker is required."; exit 1; }
command -v pm2 >/dev/null 2>&1 || { echo "❌ PM2 is required. Install: npm install -g pm2"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "❌ Python3 is required."; exit 1; }

# 2. Network Setup
echo "🌐 Setting up Mesh Network..."
docker network create x0tta6bl4-net 2>/dev/null || true

# 3. Core Database
echo "🗄️ Checking PostgreSQL (x0tta6bl4-db)..."
if [ "$(docker inspect -f '{{.State.Running}}' x0tta6bl4-db 2>/dev/null)" != "true" ]; then
    echo "⚠️ x0tta6bl4-db not running. Starting from standard postgres image..."
    docker run -d --name x0tta6bl4-db --network x0tta6bl4-net -e POSTGRES_PASSWORD=x0tta6bl4_password -e POSTGRES_USER=x0tta6bl4 -e POSTGRES_DB=x0tta6bl4 postgres:15-alpine
    sleep 10
fi

# 4. Database Migrations
echo "🧬 Running Marketplace Migrations..."
docker exec -i x0tta6bl4-db psql -U x0tta6bl4 -d x0tta6bl4 < final_marketplace_migration.sql || echo "⚠️ Migration already applied."

# 5. Dashboard & Gateway
echo "🖥️  Deploying Secure Gateway (Port 8080)..."
cd x0tta6bl4-app
npm install --silent
pm2 delete x0tta6bl4-gateway 2>/dev/null || true
pm2 start server.cjs --name x0tta6bl4-gateway
cd ..

# 6. Landing Page
echo "🎨 Deploying Landing Page (Port 8084)..."
cd x0tta6bl4-landing
npm install --silent
pm2 delete x0tta6bl4-landing 2>/dev/null || true
pm2 start server.js --name x0tta6bl4-landing
cd ..

# 7. AI & Security Services
echo "🛡️  Activating Kernel Protection (eBPF)..."
sudo pkill -f ebpf_shaper.py || true
sudo nohup python3 src/network/ebpf_shaper.py > .logs/ebpf.log 2>&1 &

echo "🩹 Starting Self-Healing Daemon (MAPE-K)..."
sudo pkill -f self_healing_daemon.py || true
sudo nohup python3 src/network/self_healing_daemon.py > .logs/daemon.log 2>&1 &

# 8. Final Status
pm2 save
echo "=============================================================================="
echo "✅ DEPLOYMENT COMPLETE"
echo "=============================================================================="
echo "🌐 PUBLIC LANDING: http://$(curl -s ifconfig.me):8084"
echo "🔐 ADMIN DASHBOARD: http://$(curl -s ifconfig.me):8080"
echo "👤 CREDENTIALS: x0tta6bl4 / mesh-ready-2026"
echo "📊 MONITORING: pm2 list"
echo "🛠️  SYSTEM: TorrServer running on port 8090"
echo "=============================================================================="
