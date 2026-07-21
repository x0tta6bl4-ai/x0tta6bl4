#!/bin/bash

set -e

# Register x0tta6bl4 workloads with SPIRE Server

SPIRE_SERVER_SOCK="/var/lib/spire/sockets/registration.sock"
TRUST_DOMAIN="x0tta6bl4.mesh"

echo "🔐 Registering x0tta6bl4 workloads with SPIRE..."

# Function to register workload
register_workload() {
    local spiffe_id=$1
    local selector=$2
    local ttl=${3:-3600}  # Default 1 hour TTL
    
    echo "  Registering: $spiffe_id (selectors: $selector)"
    
    /opt/spire/bin/spire-server entry create \
        -registrationUDS "$SPIRE_SERVER_SOCK" \
        -spiffeID "spiffe://${TRUST_DOMAIN}${spiffe_id}" \
        -selector "$selector" \
        -ttl "$ttl" 2>/dev/null || echo "    (may already exist)"
}

# Wait for socket to be available
MAX_ATTEMPTS=30
ATTEMPT=0
while [ ! -S "$SPIRE_SERVER_SOCK" ] && [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    echo "Waiting for SPIRE Server socket... ($ATTEMPT/$MAX_ATTEMPTS)"
    sleep 1
    ATTEMPT=$((ATTEMPT + 1))
done

if [ ! -S "$SPIRE_SERVER_SOCK" ]; then
    echo "❌ SPIRE Server socket not found after $MAX_ATTEMPTS attempts"
    exit 1
fi

echo "✅ SPIRE Server socket ready"
echo ""

# Register core x0tta6bl4 services
echo "📝 Registering core services:"
register_workload "/service/api" "unix:uid:0" 3600
register_workload "/service/mesh-node" "unix:uid:0" 3600
register_workload "/service/mape-k" "unix:uid:0" 3600
register_workload "/service/monitor" "unix:uid:0" 3600
register_workload "/service/daq" "unix:uid:0" 3600

echo ""
echo "📝 Registering network services:"
register_workload "/network/batman" "unix:uid:0" 3600
register_workload "/network/ebpf" "unix:uid:0" 3600
register_workload "/network/discovery" "unix:uid:0" 3600

echo ""
echo "📝 Registering security services:"
register_workload "/security/policy-engine" "unix:uid:0" 3600
register_workload "/security/threat-detection" "unix:uid:0" 3600
register_workload "/security/device-attestation" "unix:uid:0" 3600

echo ""
echo "📝 Registering ML services:"
register_workload "/ml/graphsage" "unix:uid:0" 3600
register_workload "/ml/rag-engine" "unix:uid:0" 3600
register_workload "/ml/anomaly-detector" "unix:uid:0" 3600

echo ""
echo "📝 Registering DAO services:"
register_workload "/dao/governance" "unix:uid:0" 3600
register_workload "/dao/token-bridge" "unix:uid:0" 3600
register_workload "/dao/voting" "unix:uid:0" 3600

echo ""
echo "✅ Workload registration complete!"

# List registered entries
echo ""
echo "📊 Registered entries:"
/opt/spire/bin/spire-server entry list -registrationUDS "$SPIRE_SERVER_SOCK" 2>/dev/null || true

echo ""
echo "🔐 SPIFFE/SPIRE initialization complete"
