#!/bin/sh
# SPIRE Agent entrypoint — generates a fresh join token at startup
set -e

# Generate join token via SPIRE Server API socket
# Server socket is mounted from spire-server container
TOKEN=$(spire-server token generate \
  -socketPath /tmp/spire-server/private/api.sock \
  -spiffeID spiffe://x0tta6bl4.mesh/node/local-node 2>/dev/null | grep -oP 'Token:\s*\K\S+')

if [ -z "$TOKEN" ]; then
  # Fallback: use the token baked into the config (1st run)
  echo "Could not generate token from server socket; using baked-in token"
  exec spire-agent run -config /etc/spire/agent.conf
fi

# Write temporary config with fresh token
cat /etc/spire/agent.conf | sed "s/join_token = \".*\"/join_token = \"$TOKEN\"/" > /tmp/agent.conf

exec spire-agent run -config /tmp/agent.conf
