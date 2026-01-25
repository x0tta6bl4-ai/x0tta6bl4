#!/bin/bash
# Rollback Script for Staging Deployment
# Automatically rolls back to previous stable version if critical metrics breach

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running in automatic mode
AUTO_MODE="${1:-manual}"

if [ "$AUTO_MODE" == "auto" ]; then
    log_info "🔄 Automatic rollback triggered"
    
    # Send alert
    if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
        curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
            -d "chat_id=$TELEGRAM_CHAT_ID" \
            -d "text=🚨 AUTOMATIC ROLLBACK TRIGGERED%0A%0AReason: Critical metrics breach%0ATime: $(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            > /dev/null
    fi
else
    log_info "🔄 Manual rollback initiated"
fi

# Step 1: Stop current deployment
log_info "Stopping current deployment..."
cd "$SCRIPT_DIR"

if [ -f "docker-compose.staging.yml" ]; then
    docker-compose -f docker-compose.staging.yml down
    log_info "Current deployment stopped"
else
    log_warn "docker-compose.staging.yml not found. Skipping Docker Compose rollback."
fi

# Step 2: Restore previous version
log_info "Restoring previous stable version..."

cd "$PROJECT_ROOT"

# Get previous stable tag
PREVIOUS_TAG=$(git tag --sort=-creatordate | grep -E "v[0-9]+\.[0-9]+\.[0-9]+-stable" | head -n 1)

if [ -z "$PREVIOUS_TAG" ]; then
    log_warn "No stable tag found. Using last commit."
    git checkout HEAD~1
else
    log_info "Rolling back to: $PREVIOUS_TAG"
    git checkout "$PREVIOUS_TAG"
fi

# Step 3: Rebuild and redeploy
log_info "Rebuilding images..."
docker build -f Dockerfile.app -t x0tta6bl4-app:staging .

if [ -f "Dockerfile.mesh-node" ]; then
    docker build -f Dockerfile.mesh-node -t x0tta6bl4-mesh-node:staging .
fi

# Step 4: Restart services
log_info "Restarting services..."
cd "$SCRIPT_DIR"

if [ -f "docker-compose.staging.yml" ]; then
    docker-compose -f docker-compose.staging.yml up -d
    log_info "Services restarted"
else
    log_warn "docker-compose.staging.yml not found. Manual restart required."
fi

# Step 5: Wait for health checks
log_info "Waiting for services to be healthy..."
sleep 30

# Step 6: Verify rollback
log_info "Verifying rollback..."

if [ -f "smoke_tests.sh" ]; then
    if bash smoke_tests.sh; then
        log_info "✅ Rollback successful! All health checks passing."
        
        # Send success notification
        if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
            curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
                -d "chat_id=$TELEGRAM_CHAT_ID" \
                -d "text=✅ ROLLBACK SUCCESSFUL%0A%0AVersion: $PREVIOUS_TAG%0ATime: $(date -u +%Y-%m-%dT%H:%M:%SZ)" \
                > /dev/null
        fi
        
        exit 0
    else
        log_error "❌ Rollback verification failed!"
        exit 1
    fi
else
    log_warn "smoke_tests.sh not found. Skipping verification."
    log_info "⚠️  Please manually verify the rollback."
fi

