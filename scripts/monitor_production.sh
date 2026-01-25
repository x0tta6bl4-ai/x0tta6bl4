#!/bin/bash
# Production Monitoring Script
# Monitors x0tta6bl4 v3.0.0 in production

set -euo pipefail

VPS_IP="${1:-89.125.1.107}"
VPS_USER="${2:-root}"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                                                              ║"
echo "║     📊 PRODUCTION MONITORING - x0tta6bl4 v3.0.0              ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check health
log_info "Checking health endpoint..."
HEALTH=$(sshpass -p 'tSiy6Il0gP4CIF39c4' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    $VPS_USER@$VPS_IP "curl -s http://localhost:8081/health 2>&1" || echo "ERROR")

if echo "$HEALTH" | grep -q '"status":"ok"'; then
    log_info "✅ Health: OK"
    echo "$HEALTH" | python3 -m json.tool 2>/dev/null || echo "$HEALTH"
else
    log_error "❌ Health check failed: $HEALTH"
fi

echo ""

# Check container
log_info "Checking container status..."
CONTAINER_STATUS=$(sshpass -p 'tSiy6Il0gP4CIF39c4' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    $VPS_USER@$VPS_IP "docker ps --filter name=x0t-node --format '{{.Status}}' 2>&1" || echo "ERROR")

if echo "$CONTAINER_STATUS" | grep -q "Up"; then
    log_info "✅ Container: $CONTAINER_STATUS"
else
    log_error "❌ Container status: $CONTAINER_STATUS"
fi

echo ""

# Check VPN
log_info "Checking VPN status..."
VPN_STATUS=$(sshpass -p 'tSiy6Il0gP4CIF39c4' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    $VPS_USER@$VPS_IP "systemctl is-active x-ui 2>&1" || echo "ERROR")

if [ "$VPN_STATUS" = "active" ]; then
    log_info "✅ VPN (X-UI): Active"
else
    log_warn "⚠️ VPN status: $VPN_STATUS"
fi

echo ""

# Check metrics
log_info "Checking metrics endpoint..."
METRICS_RESPONSE=$(sshpass -p 'tSiy6Il0gP4CIF39c4' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    $VPS_USER@$VPS_IP "curl -s http://localhost:8081/metrics 2>&1" || echo "")

# Check if metrics contain Prometheus format
if echo "$METRICS_RESPONSE" | grep -q "HELP\|TYPE\|gauge\|counter"; then
    METRICS_COUNT=$(echo "$METRICS_RESPONSE" | grep -c "^[^#]" || echo "0")
    log_info "✅ Metrics: Available ($METRICS_COUNT metric lines)"
else
    log_warn "⚠️ Metrics format may be different"
fi

echo ""

# Check resources
log_info "Checking system resources..."
RESOURCES=$(sshpass -p 'tSiy6Il0gP4CIF39c4' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    $VPS_USER@$VPS_IP "free -h | grep Mem | awk '{print \"RAM: \" \$3 \"/\" \$2}' && df -h / | tail -1 | awk '{print \"Disk: \" \$3 \"/\" \$2 \" (\" \$5 \" used)\"}'" 2>&1 || echo "ERROR")

log_info "System resources:"
echo "$RESOURCES"

echo ""
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_info "✅ Monitoring complete!"
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

