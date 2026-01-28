#!/bin/bash

echo "=== x0tta6bl4 AI Gateway Demo ==="
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose is not installed. Please install Docker Compose and try again."
    exit 1
fi

echo "✅ Docker and Docker Compose are available"
echo ""

# Build and start the demo
echo "🚀 Starting x0tta6bl4 AI Gateway Demo..."
docker-compose up -d

# Wait for the service to be ready
echo "⏳ Waiting for service to be ready..."
sleep 30

# Health Check
echo "🔍 Checking service health..."
if curl -s http://localhost:8000/health > /dev/null; then
    echo "✅ Service is healthy"
else
    echo "❌ Service is not healthy"
    exit 1
fi

echo ""
echo "=== Demo is ready! ==="
echo ""
echo "📊 Prometheus Metrics: http://localhost:9090"
echo "🔗 Mesh Network Status: http://localhost:8000/api/v1/mesh/nodes"
echo "🔍 Threat Detection: http://localhost:8000/api/v1/threats"
echo ""
echo "Use 'docker-compose down -v' to stop and cleanup the demo"
