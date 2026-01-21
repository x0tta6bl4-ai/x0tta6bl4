#!/bin/bash
# Production Rollback Script
# Дата: 2026-01-07
# Версия: 3.4.0-fixed2

set -euo pipefail

NAMESPACE="${NAMESPACE:-x0tta6bl4-production}"
RELEASE_NAME="${RELEASE_NAME:-x0tta6bl4}"
REVISION="${1:-}"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# List revisions
list_revisions() {
    log "Available revisions:"
    helm history "$RELEASE_NAME" -n "$NAMESPACE" || {
        error "Failed to get revision history"
        exit 1
    }
}

# Rollback
rollback() {
    if [ -z "$REVISION" ]; then
        error "Usage: $0 <revision-number>"
        error "Example: $0 3 (rollback to revision 3)"
        echo ""
        list_revisions
        exit 1
    fi
    
    log "Rolling back to revision: $REVISION"
    
    # Confirm
    read -p "This will rollback $RELEASE_NAME to revision $REVISION. Continue? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        log "Rollback cancelled"
        exit 0
    fi
    
    # Execute rollback
    helm rollback "$RELEASE_NAME" "$REVISION" -n "$NAMESPACE" || {
        error "Rollback failed"
        exit 1
    }
    
    log "✅ Rollback initiated"
    
    # Wait for rollout
    log "Waiting for rollout to complete..."
    kubectl rollout status deployment/$RELEASE_NAME -n "$NAMESPACE" || {
        error "Rollout failed"
        exit 1
    }
    
    log "✅ Rollback completed successfully"
    
    # Verify health
    log "Verifying health..."
    sleep 10
    
    if curl -sf http://localhost:8080/health > /dev/null 2>&1; then
        log "✅ Health check passed"
    else
        warn "⚠️ Health check failed (service may still be starting)"
    fi
}

# Main
main() {
    log "╔══════════════════════════════════════════════════════════════╗"
    log "║     Production Rollback Script                               ║"
    log "╚══════════════════════════════════════════════════════════════╝"
    
    if [ -z "$REVISION" ]; then
        list_revisions
    else
        rollback
    fi
}

if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    main "$@"
fi

