#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ALLOW_LOCAL_SMOKE="${X0TTA6BL4_ALLOW_LOCAL_PRODUCTION_SMOKE:-}"
CLAIM_BOUNDARY="This local production-compose smoke test checks local containers and endpoints only. It does not prove live customer traffic, traffic shifting, external DPI bypass, settlement finality, production SLOs, or production readiness."

bounded_output_metadata() {
    local label="$1"
    local value="$2"
    local bytes
    local sha
    bytes=$(printf "%s" "$value" | wc -c | tr -d ' ')
    sha=$(printf "%s" "$value" | sha256sum | awk '{print $1}')
    echo "$label output metadata: bytes=$bytes sha256=$sha raw_output_retained=false"
}

if [[ "$ALLOW_LOCAL_SMOKE" != "yes" ]]; then
    echo "LOCAL PRODUCTION-COMPOSE SMOKE: BLOCKED"
    echo "Set X0TTA6BL4_ALLOW_LOCAL_PRODUCTION_SMOKE=yes to start local production-compose services."
    echo "Claim boundary: $CLAIM_BOUNDARY"
    exit 2
fi

echo "🚀 Starting Local Production-Compose Smoke Observation for x0tta6bl4 MaaS"
echo "Claim boundary: $CLAIM_BOUNDARY"

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
    echo "✅ Control Plane API local health endpoint returned 200"
else
    echo "❌ Control Plane API failed (Status: $HTTP_STATUS)"
    CONTROL_LOGS="$(docker compose -f docker-compose.production.yml logs --tail=200 control-plane 2>&1 || true)"
    bounded_output_metadata "control-plane logs" "$CONTROL_LOGS"
    exit 1
fi

# PQC Status
PQC_ALGO=$(curl -s http://localhost:8000/pqc/status | grep -o "ML-DSA-65" || echo "NONE")
if [ "$PQC_ALGO" == "ML-DSA-65" ]; then
    echo "✅ PQC status endpoint reports ML-DSA-65 locally"
else
    echo "⚠️ PQC Layer issues detected"
fi

# Janitor status (Check if process is in logs)
JANITOR_LOGS="$(docker compose -f docker-compose.production.yml logs --tail=200 janitor 2>&1 || true)"
bounded_output_metadata "janitor logs" "$JANITOR_LOGS"
if echo "$JANITOR_LOGS" | grep -q "Janitor service started"; then
    echo "✅ Marketplace Janitor local startup marker observed"
else
    echo "❌ Janitor service failed to start"
    exit 1
fi

echo "🏁 LOCAL PRODUCTION-COMPOSE SMOKE OBSERVATION COMPLETE"
echo "This is not production deployment readiness proof."
