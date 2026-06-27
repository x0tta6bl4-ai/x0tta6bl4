#!/usr/bin/env bash
# Production monitoring observation script.
# Records remote health/resource observations; not production readiness proof.

set -euo pipefail

TARGET_HOST="${1:-${x0tta6bl4_MONITOR_HOST:-}}"
VPS_USER="${2:-${x0tta6bl4_MONITOR_USER:-root}}"
VPS_PASS="${VPS_PASS:?Set VPS_PASS in environment}"
CLAIM_BOUNDARY="Remote health, container, VPN, metrics, and resource observations do not prove live customer traffic, traffic shifting, external DPI bypass, settlement finality, production SLOs, or production readiness without separate current evidence."

if [[ -z "$TARGET_HOST" ]]; then
    echo "Usage: VPS_PASS=... $0 <host> [user]"
    echo "Or set x0tta6bl4_MONITOR_HOST and optional x0tta6bl4_MONITOR_USER."
    exit 2
fi

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                                                              ║"
echo "║     📊 PRODUCTION MONITORING OBSERVATION - x0tta6bl4         ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Claim boundary: $CLAIM_BOUNDARY"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
bounded_output_metadata() {
    local label="$1"
    local value="$2"
    local bytes
    local sha
    bytes=$(printf "%s" "$value" | wc -c | tr -d ' ')
    sha=$(printf "%s" "$value" | sha256sum | awk '{print $1}')
    log_info "$label output metadata: bytes=$bytes sha256=$sha raw_output_retained=false"
}

# Check health
log_info "Checking health endpoint..."
HEALTH=$(sshpass -p "$VPS_PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "$VPS_USER@$TARGET_HOST" "curl -s http://localhost:8081/health 2>&1" || echo "ERROR")
bounded_output_metadata "health" "$HEALTH"

if echo "$HEALTH" | grep -q '"status":"ok"'; then
    log_info "✅ Health: OK"
else
    log_error "❌ Health check failed; raw output redacted"
fi

echo ""

# Check container
log_info "Checking container status..."
CONTAINER_STATUS=$(sshpass -p "$VPS_PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "$VPS_USER@$TARGET_HOST" "docker ps --filter name=x0t-node --format '{{.Status}}' 2>&1" || echo "ERROR")
bounded_output_metadata "container_status" "$CONTAINER_STATUS"

if echo "$CONTAINER_STATUS" | grep -q "Up"; then
    log_info "✅ Container: $CONTAINER_STATUS"
else
    log_error "❌ Container status: $CONTAINER_STATUS"
fi

echo ""

# Check VPN
log_info "Checking VPN status..."
VPN_STATUS=$(sshpass -p "$VPS_PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "$VPS_USER@$TARGET_HOST" "systemctl is-active x-ui 2>&1" || echo "ERROR")

if [ "$VPN_STATUS" = "active" ]; then
    log_info "✅ VPN (X-UI): Active"
else
    log_warn "⚠️ VPN status: $VPN_STATUS"
fi

echo ""

# Check metrics
log_info "Checking metrics endpoint..."
METRICS_RESPONSE=$(sshpass -p "$VPS_PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "$VPS_USER@$TARGET_HOST" "curl -s http://localhost:8081/metrics 2>&1" || echo "")
bounded_output_metadata "metrics" "$METRICS_RESPONSE"

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
RESOURCES=$(sshpass -p "$VPS_PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "$VPS_USER@$TARGET_HOST" "free -h | grep Mem | awk '{print \"RAM: \" \$3 \"/\" \$2}' && df -h / | tail -1 | awk '{print \"Disk: \" \$3 \"/\" \$2 \" (\" \$5 \" used)\"}'" 2>&1 || echo "ERROR")

log_info "System resources:"
echo "$RESOURCES"

echo ""
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_info "✅ Monitoring observation complete; not production readiness proof."
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
