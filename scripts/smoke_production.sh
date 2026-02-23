#!/bin/bash
set -e

echo "🚀 Starting Production Smoke Test for x0tta6bl4 MaaS"

# 1. Build
echo "📦 Building containers..."
docker compose -f docker-compose.production.yml build control-plane janitor

# 2. Start Infrastructure
echo "🔋 Starting Database and Vault..."
docker compose -f docker-compose.production.yml up -d db vault redis
sleep 10

# 3. Migrate
echo "📂 Running Database Migrations..."
docker compose -f docker-compose.production.yml run --rm control-plane alembic upgrade head

# 4. Start Control Plane & Janitor
echo "🧠 Starting Application Core..."
docker compose -f docker-compose.production.yml up -d control-plane janitor
sleep 15

# 5. Verify Health
echo "🔍 Verifying Health Endpoints..."

# API Health
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health)
if [ "$HTTP_STATUS" -eq 200 ]; then
    echo "✅ Control Plane API is HEALTHY"
else
    echo "❌ Control Plane API failed (Status: $HTTP_STATUS)"
    docker compose -f docker-compose.production.yml logs control-plane
    exit 1
fi

# PQC Status
PQC_ALGO=$(curl -s http://localhost:8000/pqc/status | grep -o "ML-DSA-65" || echo "NONE")
if [ "$PQC_ALGO" == "ML-DSA-65" ]; then
    echo "✅ PQC Layer is ACTIVE (ML-DSA-65)"
else
    echo "⚠️ PQC Layer issues detected"
fi

# Janitor status (Check if process is in logs)
if docker compose -f docker-compose.production.yml logs janitor | grep -q "Janitor service started"; then
    echo "✅ Marketplace Janitor is RUNNING"
else
    echo "❌ Janitor service failed to start"
    docker-compose -f docker-compose.production.yml logs janitor
    exit 1
fi

echo "🏁 SMOKE TEST COMPLETED SUCCESSFULLY!"
echo "MaaS Enterprise is ready for deployment."
