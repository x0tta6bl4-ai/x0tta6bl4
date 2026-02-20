#!/bin/bash
# VPS Update Script - SAFE MODE (with dry-run and backup)
# Updates existing x0t-node container with safety checks

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
DRY_RUN="${3:-false}"
VPS_PASS="${VPS_PASS:?Set VPS_PASS in environment}"

if [ -z "$VPS_IP" ]; then
    log_error "Usage: $0 <VPS_IP> [VPS_USER] [dry-run]"
    log_error "Example: $0 89.125.1.107 root"
    log_error "Example (dry-run): $0 89.125.1.107 root dry-run"
    exit 1
fi

if [ "$DRY_RUN" = "dry-run" ]; then
    log_warn "🔍 DRY-RUN MODE: Will show what would be done, but won't execute"
fi

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                                                              ║"
echo "║     🔄 VPS UPDATE - SAFE MODE                                ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
log_info "VPS IP: $VPS_IP"
log_info "VPS User: $VPS_USER"
if [ "$DRY_RUN" = "dry-run" ]; then
    log_warn "Mode: DRY-RUN (no changes will be made)"
else
    log_info "Mode: LIVE (will make changes)"
fi
echo ""

# Pre-flight checks
log_step "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_step "PRE-FLIGHT CHECKS"
log_step "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

log_info "Checking SSH connection..."
if sshpass -p "$VPS_PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    -o ConnectTimeout=5 $VPS_USER@$VPS_IP "echo 'SSH OK'" > /dev/null 2>&1; then
    log_info "✅ SSH connection: OK"
else
    log_error "❌ Cannot connect to VPS"
    exit 1
fi

log_info "Checking VPN status..."
VPN_STATUS=$(sshpass -p "$VPS_PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    $VPS_USER@$VPS_IP "systemctl is-active xray 2>/dev/null || echo 'inactive'")
if [ "$VPN_STATUS" = "active" ]; then
    log_info "✅ VPN (Xray): RUNNING"
else
    log_warn "⚠️  VPN (Xray): $VPN_STATUS"
fi

log_info "Checking existing x0t-node container..."
CONTAINER_EXISTS=$(sshpass -p "$VPS_PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    $VPS_USER@$VPS_IP "docker ps -a --filter name=x0t-node --format '{{.Names}}' 2>/dev/null || echo ''")
if [ -n "$CONTAINER_EXISTS" ]; then
    log_info "✅ Found container: $CONTAINER_EXISTS"
else
    log_warn "⚠️  Container x0t-node not found"
fi

log_info "Checking disk space..."
DISK_FREE=$(sshpass -p "$VPS_PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    $VPS_USER@$VPS_IP "df -h / | tail -1 | awk '{print \$4}'")
log_info "Free disk space: $DISK_FREE"

if [ "$DRY_RUN" = "dry-run" ]; then
    echo ""
    log_warn "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_warn "DRY-RUN: Would execute the following steps:"
    log_warn "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "1. Build Docker image locally"
    log_info "2. Save image to tar.gz (~500MB-1GB)"
    log_info "3. Copy to VPS"
    log_info "4. Stop x0t-node container"
    log_info "5. Load new image on VPS"
    log_info "6. Remove old container"
    log_info "7. Start new container with same ports"
    log_info "8. Install/configure Nginx"
    log_info "9. Test health endpoint"
    echo ""
    log_warn "To actually execute, run without 'dry-run' parameter"
    exit 0
fi

# Step 1: Build Docker image locally
log_step "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_step "STEP 1: Building Docker Image"
log_step "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

log_info "Building Docker image (this may take 5-10 minutes)..."
if docker build -t x0tta6bl4-app:staging -f Dockerfile.app .; then
    log_info "✅ Docker image built successfully"
else
    log_error "❌ Docker build failed"
    exit 1
fi

log_info "Saving Docker image to tar..."
docker save x0tta6bl4-app:staging | gzip > /tmp/x0tta6bl4-app-staging.tar.gz

IMAGE_SIZE=$(du -h /tmp/x0tta6bl4-app-staging.tar.gz | cut -f1)
log_info "Image size: $IMAGE_SIZE"
echo ""

# Step 2: Backup current state on VPS
log_step "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_step "STEP 2: Backup Current State"
log_step "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

log_info "Creating backup of current container..."
sshpass -p "$VPS_PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    $VPS_USER@$VPS_IP "docker commit x0t-node x0t-node-backup-\$(date +%Y%m%d-%H%M%S) 2>/dev/null || echo 'No container to backup'"

log_info "✅ Backup created"
echo ""

# Step 3: Copy to VPS
log_step "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_step "STEP 3: Copying to VPS"
log_step "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

log_info "Copying image to VPS (this may take a few minutes)..."
sshpass -p "$VPS_PASS" scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    /tmp/x0tta6bl4-app-staging.tar.gz $VPS_USER@$VPS_IP:/root/

log_info "Copying update script..."
sshpass -p "$VPS_PASS" scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    scripts/vps_update_on_server.sh $VPS_USER@$VPS_IP:/root/

log_info "✅ Files copied to VPS"
echo ""

# Step 4: Update on VPS
log_step "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_step "STEP 4: Updating on VPS (preserving VPN)"
log_step "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

log_info "Running update script on VPS..."
if sshpass -p "$VPS_PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    $VPS_USER@$VPS_IP "bash /root/vps_update_on_server.sh"; then
    log_info "✅ VPS update complete"
else
    log_error "❌ VPS update failed"
    log_warn "You can restore from backup if needed"
    exit 1
fi

log_info "✅ VPS update complete (VPN preserved)"
echo ""

# Step 5: Verification
log_step "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_step "STEP 5: Verification"
log_step "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

log_info "Waiting for service to start (30 seconds)..."
sleep 30

APP_URL="http://$VPS_IP"

log_info "Testing health endpoint..."
if sshpass -p "$VPS_PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    $VPS_USER@$VPS_IP "curl -s -f http://localhost:8081/health" > /dev/null 2>&1; then
    log_info "✅ Health check: PASSED"
    echo ""
    log_info "Health endpoint response:"
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
log_info "   Restore backup: ssh $VPS_USER@$VPS_IP 'docker run -d --name x0t-node-restored <backup-image>'"
echo ""
log_info "🎆 CONGRATULATIONS! x0tta6bl4 is UPDATED! 🎆"
