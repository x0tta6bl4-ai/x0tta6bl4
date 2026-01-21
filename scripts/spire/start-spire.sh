#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "Starting SPIRE infrastructure..."

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "Error: docker-compose is required but not installed"
    exit 1
fi

# Check if Docker daemon is running
if ! docker info &> /dev/null; then
    echo "Error: Docker daemon is not running"
    exit 1
fi

# Create necessary directories
mkdir -p /tmp/spire-agent/public
chmod 777 /tmp/spire-agent/public

# Start SPIRE services
echo "Starting SPIRE server and agent..."
cd "$PROJECT_DIR"
docker-compose -f docker-compose.spire.yml up -d

# Wait for SPIRE services to be ready
echo "Waiting for SPIRE services to be ready..."
MAX_RETRIES=30
RETRY_INTERVAL=2
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
    docker-compose -f docker-compose.spire.yml logs
    exit 1
fi

echo "SPIRE infrastructure is ready!"
echo ""
echo "To stop SPIRE:"
echo "  docker-compose -f docker-compose.spire.yml down"
echo ""
echo "To run tests with SPIRE:"
echo "  pytest tests/integration/test_spire_integration.py -v"
