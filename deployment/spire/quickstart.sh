#!/bin/bash
# Quick start script for SPIRE deployment
# Usage: ./quickstart.sh [docker|k8s]

set -e

DEPLOYMENT_TYPE="${1:-docker}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🔐 SPIRE Quick Start for x0tta6bl4"
echo "=================================="
echo ""

case "$DEPLOYMENT_TYPE" in
    docker)
        echo "📦 Deploying SPIRE with Docker Compose..."
        
        # Check Docker
        if ! command -v docker &> /dev/null; then
            echo "❌ Docker is not installed"
            exit 1
        fi
        
        if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
            echo "❌ Docker Compose is not installed"
            exit 1
        fi
        
        # Generate join token
        JOIN_TOKEN=$(openssl rand -hex 32)
        export SPIRE_JOIN_TOKEN="$JOIN_TOKEN"
        
        echo "Generated join token: $JOIN_TOKEN"
        echo ""
        
        # Start SPIRE
        cd "$SCRIPT_DIR"
        docker compose up -d
        
        echo ""
        echo "✅ SPIRE deployed!"
        echo ""
        echo "Wait for SPIRE to be ready:"
        echo "  docker compose logs -f spire-server"
        echo ""
        echo "Create workload entry:"
        echo "  docker exec -it spire-server spire-server entry create \\"
        echo "    -spiffeID spiffe://x0tta6bl4.mesh/workload/x0tta6bl4-node \\"
        echo "    -parentID spiffe://x0tta6bl4.mesh/spire/agent/docker \\"
        echo "    -selector docker:label:app:x0tta6bl4-node"
        echo ""
        echo "Check SPIRE Agent socket:"
        echo "  docker exec -it spire-agent ls -la /run/spire/sockets/"
        ;;
        
    k8s)
        echo "📦 Deploying SPIRE to Kubernetes..."
        
        # Check kubectl
        if ! command -v kubectl &> /dev/null; then
            echo "❌ kubectl is not installed"
            exit 1
        fi
        
        # Check helm
        if ! command -v helm &> /dev/null; then
            echo "❌ helm is not installed"
            exit 1
        fi
        
        # Create namespace
        kubectl create namespace spire-system --dry-run=client -o yaml | kubectl apply -f -
        
        # Deploy with Helm
        cd "$SCRIPT_DIR/helm/spire"
        helm upgrade --install spire . \
            --namespace spire-system \
            --set global.trustDomain=x0tta6bl4.mesh
        
        echo ""
        echo "✅ SPIRE deployed to Kubernetes!"
        echo ""
        echo "Check deployment:"
        echo "  kubectl get pods -n spire-system"
        echo ""
        echo "Create workload entry:"
        echo "  kubectl exec -n spire-system spire-server-0 -- spire-server entry create \\"
        echo "    -spiffeID spiffe://x0tta6bl4.mesh/workload/x0tta6bl4-node \\"
        echo "    -parentID spiffe://x0tta6bl4.mesh/spire/agent/k8s/psat/node_name \\"
        echo "    -selector k8s:ns:x0tta6bl4 \\"
        echo "    -selector k8s:sa:x0tta6bl4-node"
        ;;
        
    *)
        echo "Usage: $0 [docker|k8s]"
        echo ""
        echo "  docker - Deploy with Docker Compose (development)"
        echo "  k8s    - Deploy to Kubernetes with Helm (production)"
        exit 1
        ;;
esac
