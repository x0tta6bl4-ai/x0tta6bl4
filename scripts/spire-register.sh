#!/bin/bash
# Register SPIRE workload entries for x0tta6bl4 mesh nodes.
# Run after SPIRE server is healthy:
#   docker compose -f docker-compose.spire.yml exec spire-server /bin/sh -c "$(cat scripts/spire-register.sh)"

set -e

TRUST_DOMAIN="x0tta6bl4.mesh"

echo "Registering workload entries for trust domain: ${TRUST_DOMAIN}"

# Node A
spire-server entry create \
  -spiffeID "spiffe://${TRUST_DOMAIN}/node/node-a" \
  -parentID "spiffe://${TRUST_DOMAIN}/agent" \
  -selector unix:uid:1000 \
  -ttl 3600

# Node B
spire-server entry create \
  -spiffeID "spiffe://${TRUST_DOMAIN}/node/node-b" \
  -parentID "spiffe://${TRUST_DOMAIN}/agent" \
  -selector unix:uid:1000 \
  -ttl 3600

# Node C
spire-server entry create \
  -spiffeID "spiffe://${TRUST_DOMAIN}/node/node-c" \
  -parentID "spiffe://${TRUST_DOMAIN}/agent" \
  -selector unix:uid:1000 \
  -ttl 3600

# FL Coordinator (on node-a)
spire-server entry create \
  -spiffeID "spiffe://${TRUST_DOMAIN}/service/fl-coordinator" \
  -parentID "spiffe://${TRUST_DOMAIN}/agent" \
  -selector unix:uid:1000 \
  -ttl 3600

echo "Workload entries registered successfully."
spire-server entry show
