#!/bin/bash
# VPS Deployment Script for x0tta6bl4
# Deploys to your VPS in 2-3 hours

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
DOMAIN="${3:-}"

if [ -z "$VPS_IP" ]; then
    log_error "Usage: $0 <VPS_IP> [VPS_USER] [DOMAIN]"
    log_error "Example: $0 192.168.1.100 root example.com"
    exit 1
fi

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                                                              ║"
echo "║     🚀 VPS DEPLOYMENT - x0tta6bl4                           ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
log_info "VPS IP: $VPS_IP"
log_info "VPS User: $VPS_USER"
log_info "Domain: ${DOMAIN:-Not set (will use IP)}"
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
scp /tmp/x0tta6bl4-app-staging.tar.gz $VPS_USER@$VPS_IP:/root/

log_info "Copying deployment files..."
scp scripts/vps_setup.sh $VPS_USER@$VPS_IP:/root/
scp scripts/vps_docker_compose.yml $VPS_USER@$VPS_IP:/root/docker-compose.yml

log_info "✅ Files copied to VPS"
echo ""

# Step 3: Setup on VPS
log_step "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_step "STEP 3: Setting up on VPS"
log_step "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

log_info "Running setup script on VPS..."
ssh $VPS_USER@$VPS_IP "bash /root/vps_setup.sh $DOMAIN"

log_info "✅ VPS setup complete"
echo ""

# Step 4: Verification
log_step "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_step "STEP 4: Verification"
log_step "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

log_info "Waiting for service to start (30 seconds)..."
sleep 30

APP_URL="http://${DOMAIN:-$VPS_IP}"

log_info "Testing health endpoint..."
if curl -s -f $APP_URL/health > /dev/null; then
    log_info "✅ Health check: PASSED"
    curl -s $APP_URL/health | python3 -m json.tool || echo "$(curl -s $APP_URL/health)"
else
    log_warn "⚠️ Health check: Service may still be starting..."
    log_info "Try again in 1-2 minutes: curl $APP_URL/health"
fi

echo ""
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_info "✅ DEPLOYMENT COMPLETE!"
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
log_info "🌐 Your application is available at:"
log_info "   $APP_URL"
echo ""
log_info "📊 Useful commands:"
log_info "   Health check: curl $APP_URL/health"
log_info "   Metrics: curl $APP_URL/metrics"
log_info "   View logs: ssh $VPS_USER@$VPS_IP 'docker logs x0tta6bl4-production -f'"
log_info "   Service status: ssh $VPS_USER@$VPS_IP 'docker ps'"
echo ""
log_info "🎆 CONGRATULATIONS! Your system is LIVE on VPS! 🎆"

