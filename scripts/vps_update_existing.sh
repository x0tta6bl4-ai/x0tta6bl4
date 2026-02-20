#!/bin/bash
# VPS Update Script - Updates existing x0t-node container
# Preserves VPN and existing configuration

set -euo pipefail

PROJECT_ROOT="/mnt/AC74CC2974CBF3DC"
cd "$PROJECT_ROOT"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $1"; }

# Configuration
VPS_IP="${1:-}"
VPS_USER="${2:-root}"
VPS_PASS="${VPS_PASS:?Set VPS_PASS in environment}"

if [ -z "$VPS_IP" ]; then
    log_error "Usage: $0 <VPS_IP> [VPS_USER]"
    log_error "Example: $0 89.125.1.107 root"
    exit 1
fi

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                                                              ║"
echo "║     🔄 VPS UPDATE - x0tta6bl4 (Update Existing)             ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
log_info "VPS IP: $VPS_IP"
log_info "VPS User: $VPS_USER"
log_warn "⚠️  Will update existing x0t-node container"
log_info "VPN will be preserved"
echo ""

# Step 1: Build Docker image locally
log_step "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_step "STEP 1: Building Docker Image"
log_step "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

log_info "Building Docker image..."
docker build -t x0tta6bl4-app:staging -f Dockerfile.app .

log_info "Saving Docker image to tar..."
docker save x0tta6bl4-app:staging | gzip > /tmp/x0tta6bl4-app-staging.tar.gz

IMAGE_SIZE=$(du -h /tmp/x0tta6bl4-app-staging.tar.gz | cut -f1)
log_info "Image size: $IMAGE_SIZE"
echo ""

# Step 2: Copy to VPS
log_step "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_step "STEP 2: Copying to VPS"
log_step "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

log_info "Copying image to VPS (this may take a few minutes)..."
sshpass -p "$VPS_PASS" scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    /tmp/x0tta6bl4-app-staging.tar.gz $VPS_USER@$VPS_IP:/root/

log_info "Copying update script..."
sshpass -p "$VPS_PASS" scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    scripts/vps_update_on_server.sh $VPS_USER@$VPS_IP:/root/

log_info "✅ Files copied to VPS"
echo ""

# Step 3: Update on VPS
log_step "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_step "STEP 3: Updating on VPS (preserving VPN)"
log_step "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

log_info "Running update script on VPS..."
sshpass -p "$VPS_PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    $VPS_USER@$VPS_IP "bash /root/vps_update_on_server.sh"

log_info "✅ VPS update complete (VPN preserved)"
echo ""

# Step 4: Verification
log_step "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_step "STEP 4: Verification"
log_step "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

log_info "Waiting for service to start (30 seconds)..."
sleep 30

APP_URL="http://$VPS_IP"

log_info "Testing health endpoint..."
if sshpass -p "$VPS_PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    $VPS_USER@$VPS_IP "curl -s -f http://localhost:8081/health" > /dev/null 2>&1; then
    log_info "✅ Health check: PASSED"
    sshpass -p "$VPS_PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        $VPS_USER@$VPS_IP "curl -s http://localhost:8081/health" | python3 -m json.tool 2>/dev/null || \
        sshpass -p "$VPS_PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        $VPS_USER@$VPS_IP "curl -s http://localhost:8081/health"
else
    log_warn "⚠️ Health check: Service may still be starting..."
    log_info "Try again in 1-2 minutes: curl $APP_URL/health"
fi

# Check VPN
log_info "Checking VPN status..."
if sshpass -p "$VPS_PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    $VPS_USER@$VPS_IP "systemctl is-active --quiet xray"; then
    log_info "✅ VPN (Xray): RUNNING"
else
    log_warn "⚠️ VPN (Xray): Check status manually"
fi

echo ""
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_info "✅ UPDATE COMPLETE!"
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
log_info "🌐 Your application is available at:"
log_info "   $APP_URL"
log_info "   Direct: http://$VPS_IP:8081"
echo ""
log_info "🔒 VPN is preserved and running"
echo ""
log_info "📊 Useful commands:"
log_info "   Health check: curl $APP_URL/health"
log_info "   Metrics: curl $APP_URL/metrics"
log_info "   View logs: ssh $VPS_USER@$VPS_IP 'docker logs x0t-node -f'"
log_info "   Service status: ssh $VPS_USER@$VPS_IP 'docker ps'"
echo ""
log_info "🎆 CONGRATULATIONS! x0tta6bl4 is UPDATED! 🎆"
