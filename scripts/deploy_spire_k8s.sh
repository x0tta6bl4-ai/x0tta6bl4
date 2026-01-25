#!/bin/bash
# Deploy SPIRE Server and Agent to Kubernetes

set -e

echo "🚀 Deploying SPIRE to Kubernetes..."

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl not found. Please install kubectl first."
    exit 1
fi

# Check if cluster is accessible
if ! kubectl cluster-info &> /dev/null; then
    echo "❌ Cannot connect to Kubernetes cluster. Please check your kubeconfig."
    exit 1
fi

echo "✅ Kubernetes cluster accessible"

# Create namespace
echo "📦 Creating namespace..."
kubectl create namespace spire --dry-run=client -o yaml | kubectl apply -f -

# Deploy SPIRE Server
echo "🔧 Deploying SPIRE Server..."
kubectl apply -f infra/security/spire-server-deployment.yaml -n spire

# Wait for SPIRE Server to be ready
echo "⏳ Waiting for SPIRE Server to be ready..."
kubectl wait --for=condition=ready pod -l app=spire-server -n spire --timeout=300s

# Get SPIRE Server service
SPIRE_SERVER=$(kubectl get svc -n spire -l app=spire-server -o jsonpath='{.items[0].metadata.name}')
echo "✅ SPIRE Server ready: $SPIRE_SERVER"

# Deploy SPIRE Agent
echo "🔧 Deploying SPIRE Agent..."
kubectl apply -f infra/security/spire-agent-daemonset.yaml -n spire

# Wait for SPIRE Agents to be ready
echo "⏳ Waiting for SPIRE Agents to be ready..."
kubectl wait --for=condition=ready pod -l app=spire-agent -n spire --timeout=300s

# Get agent count
AGENT_COUNT=$(kubectl get pods -n spire -l app=spire-agent --no-headers | wc -l)
echo "✅ SPIRE Agents ready: $AGENT_COUNT agents"

# Check status
echo ""
echo "📊 SPIRE Deployment Status:"
echo "=========================="
kubectl get pods -n spire
echo ""
kubectl get svc -n spire

echo ""
echo "✅ SPIRE deployment complete!"
echo ""
echo "📋 Next steps:"
echo "   1. Check logs: kubectl logs -n spire -l app=spire-server"
echo "   2. Check agent logs: kubectl logs -n spire -l app=spire-agent"
echo "   3. Test connection: kubectl exec -n spire -l app=spire-server -- spire-server healthcheck"

