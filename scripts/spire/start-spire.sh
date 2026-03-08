#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
SERVER_SPIFFE_ID="spiffe://x0tta6bl4.mesh/agent/local"
WORKLOAD_SPIFFE_ID="spiffe://x0tta6bl4.mesh/workload/local-test"
DOCKER_HOST="${DOCKER_HOST:-unix:///run/docker.sock}"

echo "Starting SPIRE infrastructure..."

# Select compose command: prefer docker compose plugin, fallback to docker-compose
if docker compose version &> /dev/null; then
    COMPOSE_CMD=(docker compose)
elif command -v docker-compose &> /dev/null; then
    COMPOSE_CMD=(docker-compose)
else
    echo "Error: Docker Compose is required but not installed"
    exit 1
fi

# Check if Docker daemon is running
if ! DOCKER_HOST="$DOCKER_HOST" docker info &> /dev/null; then
    echo "Error: Docker daemon is not running"
    exit 1
fi

# Create necessary directories
mkdir -p /tmp/spire-agent/public
chmod 777 /tmp/spire-agent/public

# Start SPIRE server
echo "Starting SPIRE server..."
cd "$PROJECT_DIR"
DOCKER_HOST="$DOCKER_HOST" "${COMPOSE_CMD[@]}" -f docker-compose.spire.yml up -d spire-server

# Wait for server process
echo "Waiting for SPIRE server process to start..."
MAX_RETRIES=30
RETRY_INTERVAL=2
RETRIES=0
while [ $RETRIES -lt $MAX_RETRIES ]; do
    STATUS="$(DOCKER_HOST="$DOCKER_HOST" docker inspect --format '{{.State.Status}}' spire-server 2>/dev/null || true)"
    if [ "$STATUS" = "running" ]; then
        echo "SPIRE server is running"
        break
    fi
    RETRIES=$((RETRIES + 1))
    echo "Waiting for SPIRE server process... (attempt $RETRIES/$MAX_RETRIES)"
    sleep $RETRY_INTERVAL
done

if [ $RETRIES -eq $MAX_RETRIES ]; then
    echo "Error: SPIRE server failed to start"
    DOCKER_HOST="$DOCKER_HOST" "${COMPOSE_CMD[@]}" -f docker-compose.spire.yml logs spire-server
    exit 1
fi

# Generate join token for agent attestation
echo "Generating SPIRE join token..."
JOIN_TOKEN=""
RETRIES=0
while [ $RETRIES -lt $MAX_RETRIES ]; do
  JOIN_TOKEN="$(
      DOCKER_HOST="$DOCKER_HOST" "${COMPOSE_CMD[@]}" -f docker-compose.spire.yml exec -T spire-server \
        /opt/spire/bin/spire-server token generate \
          -socketPath /tmp/spire-server/private/api.sock \
          -spiffeID "$SERVER_SPIFFE_ID" \
      | awk -F': ' '/Token:/ {print $2}' | tr -d '\r' | tail -n1
  )"
  if [ -n "$JOIN_TOKEN" ]; then
    break
  fi
  RETRIES=$((RETRIES + 1))
  sleep $RETRY_INTERVAL
done

if [ -z "$JOIN_TOKEN" ]; then
    echo "Error: Failed to generate SPIRE join token"
    DOCKER_HOST="$DOCKER_HOST" "${COMPOSE_CMD[@]}" -f docker-compose.spire.yml logs spire-server
    exit 1
fi

# Start SPIRE agent with join token
echo "Starting SPIRE agent..."
SPIRE_JOIN_TOKEN="$JOIN_TOKEN" DOCKER_HOST="$DOCKER_HOST" "${COMPOSE_CMD[@]}" -f docker-compose.spire.yml up -d spire-agent

# Wait for SPIRE services to be ready
echo "Waiting for SPIRE services to be ready..."
RETRIES=0

while [ $RETRIES -lt $MAX_RETRIES ]; do
    if [ -S /tmp/spire-agent/public/api.sock ]; then
        echo "SPIRE agent socket is available"
        break
    fi
    
    RETRIES=$((RETRIES + 1))
    echo "Waiting for SPIRE... (attempt $RETRIES/$MAX_RETRIES)"
    sleep $RETRY_INTERVAL
done

if [ $RETRIES -eq $MAX_RETRIES ]; then
    echo "Error: SPIRE agent failed to start within timeout"
    DOCKER_HOST="$DOCKER_HOST" "${COMPOSE_CMD[@]}" -f docker-compose.spire.yml logs spire-server spire-agent
    exit 1
fi

# Get the agent's actual SPIFFE ID after attestation.
# With join_token attestation the ID is spiffe://<domain>/spire/agent/join_token/<uuid>,
# NOT the hardcoded SERVER_SPIFFE_ID. Using wrong parentID causes PERMISSION_DENIED.
echo "Retrieving agent SPIFFE ID after attestation..."
AGENT_SPIFFE_ID=""
RETRIES=0
while [ $RETRIES -lt $MAX_RETRIES ]; do
  AGENT_SPIFFE_ID=$(
    DOCKER_HOST="$DOCKER_HOST" "${COMPOSE_CMD[@]}" -f docker-compose.spire.yml exec -T spire-server \
      /opt/spire/bin/spire-server agent list \
        -socketPath /tmp/spire-server/private/api.sock \
      2>/dev/null | grep -oE "spiffe://[^[:space:]]+" | head -1 || true
  )
  if [ -n "$AGENT_SPIFFE_ID" ]; then
    echo "Agent SPIFFE ID: $AGENT_SPIFFE_ID"
    break
  fi
  RETRIES=$((RETRIES + 1))
  echo "Waiting for agent attestation... (attempt $RETRIES/$MAX_RETRIES)"
  sleep $RETRY_INTERVAL
done

if [ -z "$AGENT_SPIFFE_ID" ]; then
  echo "Warning: could not determine agent SPIFFE ID; falling back to SERVER_SPIFFE_ID"
  AGENT_SPIFFE_ID="$SERVER_SPIFFE_ID"
fi

# Register workload entries for local user, root, and common CI UIDs.
echo "Registering workload entries..."
CURRENT_UID="$(id -u)"
for UID_SELECTOR in "$CURRENT_UID" "0" "1001"; do
  DOCKER_HOST="$DOCKER_HOST" "${COMPOSE_CMD[@]}" -f docker-compose.spire.yml exec -T spire-server \
    /opt/spire/bin/spire-server entry create \
      -parentID "$AGENT_SPIFFE_ID" \
      -spiffeID "${WORKLOAD_SPIFFE_ID}-${UID_SELECTOR}" \
      -selector "unix:uid:${UID_SELECTOR}" \
      -socketPath /tmp/spire-server/private/api.sock \
    > /dev/null 2>&1 || true
done

echo "SPIRE infrastructure is ready!"
echo ""
echo "To stop SPIRE:"
echo "  DOCKER_HOST=$DOCKER_HOST ${COMPOSE_CMD[*]} -f docker-compose.spire.yml down"
echo ""
echo "To run tests with SPIRE:"
echo "  pytest tests/integration/test_spire_integration.py -v"
