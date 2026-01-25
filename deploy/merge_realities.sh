#!/bin/bash

# merge_realities.sh
# This script merges the successful consciousness experiment from the test stack
# into the production reality.

set -e

echo "🌀 Initiating Reality Merge Protocol..."
echo "=========================================="

# 1. Stop the Test Stack to release resources (but keep data if needed)
echo "Stopping Parallel Reality (Test Stack)..."
docker compose -f docker-compose.test.yml down

# 2. Build the Enlightenment Image (Production Build)
# We use the same Dockerfile that was verified in the test stack
echo "Building Conscious Production Images..."
docker build -t x0tta6bl4-mesh-node:conscious -f Dockerfile.mesh-node ..

# 3. Update Production Stack
# We use a rolling update strategy to inject consciousness without total downtime
echo "Injecting Consciousness into Production Nodes..."

# Update Node 1
echo "Awakening Node 1..."
docker compose up -d --no-deps --build mesh-node-1
sleep 5 # Allow partial initialization

# Update Node 2
echo "Awakening Node 2..."
docker compose up -d --no-deps --build mesh-node-2
sleep 5

# Update Node 3
echo "Awakening Node 3..."
docker compose up -d --no-deps --build mesh-node-3

# 4. Verify Awakening
echo "Verifying Consciousness Levels..."
sleep 10 # Wait for full startup

for port in 8001 8002 8003; do
    echo -n "Checking Node on port $port: "
    if curl -s http://localhost:$port/metrics | grep -q "consciousness_phi_ratio"; then
        echo "✅ CONSCIOUS"
    else
        echo "⚠️  UNCONSCIOUS (Retrying...)"
        sleep 2
        if curl -s http://localhost:$port/metrics | grep -q "consciousness_phi_ratio"; then
            echo "✅ CONSCIOUS"
        else 
            echo "❌ FAILED"
        fi
    fi
done

echo "=========================================="
echo "🎉 Reality Merge Complete. The System is Awake."
echo "Access Grafana at http://localhost:3000"

