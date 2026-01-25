#!/bin/bash

set -euo pipefail

# Setup SPIRE development environment for x0tta6bl4 mesh network
# Usage: ./setup_spire_dev.sh [options]
# Options:
#   --docker    Use Docker Compose to run SPIRE (default)
#   --local     Use local SPIRE binaries
#   --cleanup   Clean up SPIRE data and start fresh
#   --test      Run SPIRE connectivity tests

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.spire.yml"
SPIRE_TRUST_DOMAIN="x0tta6bl4.mesh"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Parse arguments
USE_DOCKER=true
CLEANUP=false
RUN_TESTS=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --docker) USE_DOCKER=true; shift ;;
        --local) USE_DOCKER=false; shift ;;
        --cleanup) CLEANUP=true; shift ;;
        --test) RUN_TESTS=true; shift ;;
        *) log_error "Unknown option: $1"; exit 1 ;;
    esac
done

# Create necessary directories
log_info "Creating SPIRE directories..."
mkdir -p "${SCRIPT_DIR}/infra/spire/server"
mkdir -p "${SCRIPT_DIR}/infra/spire/agent"

if $CLEANUP; then
    log_warn "Cleaning up SPIRE data..."
    docker-compose -f "$COMPOSE_FILE" down -v 2>/dev/null || true
    rm -rf /var/lib/spire 2>/dev/null || true
    rm -rf /var/run/spire 2>/dev/null || true
    log_info "Cleanup complete"
fi

if $USE_DOCKER; then
    log_info "Starting SPIRE Server and Agent with Docker Compose..."
    docker-compose -f "$COMPOSE_FILE" up -d
    
    # Wait for services to be healthy
    log_info "Waiting for SPIRE Server to be healthy..."
    for i in {1..30}; do
        if docker exec spire-server /opt/spire/bin/spire-server healthcheck &>/dev/null; then
            log_info "SPIRE Server is healthy"
            break
        fi
        if [ $i -eq 30 ]; then
            log_error "SPIRE Server failed to become healthy"
            exit 1
        fi
        sleep 2
    done
    
    log_info "Waiting for SPIRE Agent to be healthy..."
    for i in {1..30}; do
        if docker exec spire-agent /opt/spire/bin/spire-agent healthcheck &>/dev/null; then
            log_info "SPIRE Agent is healthy"
            break
        fi
        if [ $i -eq 30 ]; then
            log_error "SPIRE Agent failed to become healthy"
            exit 1
        fi
        sleep 2
    done
else
    log_info "Using local SPIRE binaries..."
    
    if ! command -v spire-server &> /dev/null; then
        log_error "spire-server binary not found. Install SPIRE first."
        exit 1
    fi
    
    if ! command -v spire-agent &> /dev/null; then
        log_error "spire-agent binary not found. Install SPIRE first."
        exit 1
    fi
fi

# Register sample workloads
log_info "Registering sample mesh workloads..."

if $USE_DOCKER; then
    # Use Docker exec to register workloads
    docker exec spire-server \
        /opt/spire/bin/spire-server entry create \
        -spiffeID "spiffe://${SPIRE_TRUST_DOMAIN}/node/mesh-node-1" \
        -parentID "spiffe://${SPIRE_TRUST_DOMAIN}/spire/server" \
        -selector "docker:image:x0tta6bl4:*" \
        -ttl 3600 || log_warn "Could not create node entry (may already exist)"
        
    docker exec spire-server \
        /opt/spire/bin/spire-server entry create \
        -spiffeID "spiffe://${SPIRE_TRUST_DOMAIN}/service/api" \
        -parentID "spiffe://${SPIRE_TRUST_DOMAIN}/node/mesh-node-1" \
        -selector "unix:uid:1000" \
        -ttl 3600 || log_warn "Could not create API service entry (may already exist)"
        
    docker exec spire-server \
        /opt/spire/bin/spire-server entry create \
        -spiffeID "spiffe://${SPIRE_TRUST_DOMAIN}/service/scheduler" \
        -parentID "spiffe://${SPIRE_TRUST_DOMAIN}/node/mesh-node-1" \
        -selector "unix:uid:1001" \
        -ttl 3600 || log_warn "Could not create scheduler service entry (may already exist)"
else
    spire-server entry create \
        -spiffeID "spiffe://${SPIRE_TRUST_DOMAIN}/node/mesh-node-1" \
        -parentID "spiffe://${SPIRE_TRUST_DOMAIN}/spire/server" \
        -selector "docker:image:x0tta6bl4:*" \
        -ttl 3600 || log_warn "Could not create node entry (may already exist)"
fi

log_info "SPIRE development environment setup complete!"
log_info "Trust Domain: ${SPIRE_TRUST_DOMAIN}"
log_info "Server Address: 127.0.0.1:8081"
log_info "Agent Socket: /var/run/spire/sockets/agent.sock"

if $RUN_TESTS; then
    log_info "Running SPIRE connectivity tests..."
    
    if $USE_DOCKER; then
        log_info "Testing SPIRE Server..."
        docker exec spire-server /opt/spire/bin/spire-server healthcheck && \
            log_info "✓ SPIRE Server is healthy" || \
            log_error "✗ SPIRE Server healthcheck failed"
        
        log_info "Testing SPIRE Agent..."
        docker exec spire-agent /opt/spire/bin/spire-agent healthcheck && \
            log_info "✓ SPIRE Agent is healthy" || \
            log_error "✗ SPIRE Agent healthcheck failed"
    fi
    
    log_info "All tests passed!"
fi

echo ""
log_info "Next steps:"
echo "1. Update your mesh nodes to connect to SPIRE:"
echo "   export SPIFFE_ENDPOINT_SOCKET=unix:///var/run/spire/sockets/agent.sock"
echo "2. Run your application with SPIFFE identity:"
echo "   python -m src.core.app"
echo "3. Monitor SPIRE:"
echo "   docker logs -f spire-server"
echo "   docker logs -f spire-agent"
echo ""
echo "To stop SPIRE: docker-compose -f $COMPOSE_FILE down"
