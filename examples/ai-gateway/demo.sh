#!/bin/bash

echo "============================================="
echo "x0tta6bl4 AI Gateway Demo"
echo "============================================="
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Check if Docker Compose is available
if ! command -v docker-compose > /dev/null 2>&1; then
    echo "❌ docker-compose is not available. Please install Docker Compose."
    exit 1
fi

# Build the image if it doesn't exist
if ! docker images | grep -q x0tta6bl4:staging; then
    echo "📦 Building x0tta6bl4:staging image..."
    cd /mnt/projects
    docker build -t x0tta6bl4:staging -f Dockerfile.app .
    if [ $? -ne 0 ]; then
        echo "❌ Failed to build image"
        exit 1
    fi
    cd - > /dev/null
fi

echo "🚀 Starting x0tta6bl4 AI Gateway..."
docker-compose up -d

echo ""
echo "⏳ Waiting for services to start..."
sleep 30

echo ""
echo "📊 Checking service health..."

# Check if both nodes are healthy
if curl -s http://localhost:8081/health | grep -q '"status": "ok"'; then
    echo "✅ Node 1 is healthy"
else
    echo "❌ Node 1 is unhealthy"
    docker-compose logs x0tta6bl4-node1
    exit 1
fi

if curl -s http://localhost:8082/health | grep -q '"status": "ok"'; then
    echo "✅ Node 2 is healthy"
else
    echo "❌ Node 2 is unhealthy"
    docker-compose logs x0tta6bl4-node2
    exit 1
fi

echo ""
echo "🔗 AI Gateway Demo URLs:"
echo "======================"
echo "Node 1 API:    http://localhost:8081"
echo "Node 1 Health: http://localhost:8081/health"
echo "Node 2 API:    http://localhost:8082"
echo "Node 2 Health: http://localhost:8082/health"
echo "Prometheus:    http://localhost:9090"
echo "Grafana:       http://localhost:3000 (admin/admin)"
echo ""

echo "🎯 Next Steps:"
echo "============="
echo "1. Test the AI gateway endpoint:"
echo "   curl -X POST http://localhost:8081/api/v1/chat -H \"Content-Type: application/json\" -d '{\"message\":\"Hello, world!\"}'"
echo ""
echo "2. Simulate a node failure:"
echo "   docker stop x0tta6bl4-node1"
echo ""
echo "3. Check if the mesh heals (wait ~30 seconds):"
echo "   curl -s http://localhost:8082/health"
echo ""
echo "4. Restore the failed node:"
echo "   docker start x0tta6bl4-node1"
echo ""
echo "5. View metrics in Prometheus:"
echo "   Open http://localhost:9090 in your browser"
echo "   Query: x0tta6bl4_node_health"
echo ""
echo "6. Stop the demo:"
echo "   docker-compose down"
