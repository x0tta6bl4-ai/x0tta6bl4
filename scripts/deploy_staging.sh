#!/bin/bash
# Deployment script for staging environment
# Usage: ./scripts/deploy_staging.sh [version]

set -e

VERSION=${1:-"latest"}
NAMESPACE="x0tta6bl4-staging"
CHART_PATH="./helm/x0tta6bl4"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     Staging Deployment Script                                 ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check prerequisites
echo "📋 Checking prerequisites..."
command -v kubectl >/dev/null 2>&1 || { echo "❌ kubectl not found"; exit 1; }
command -v helm >/dev/null 2>&1 || { echo "❌ helm not found"; exit 1; }

# Check kubectl connection
if ! kubectl cluster-info >/dev/null 2>&1; then
    echo "❌ Cannot connect to Kubernetes cluster"
    exit 1
fi

echo "✅ Prerequisites OK"
echo ""

# Create namespace if not exists
echo "📦 Creating namespace..."
kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -

# Check dependency health
echo "🔍 Checking dependency health..."
python3 scripts/check_dependencies.py || echo "⚠️  Some dependencies may be unavailable"

# Deploy with Helm
echo "🚀 Deploying x0tta6bl4 to staging..."
helm upgrade --install x0tta6bl4 $CHART_PATH \
    --namespace $NAMESPACE \
    --create-namespace \
    --set image.tag=$VERSION \
    --set production.enabled=false \
    --set replicaCount=2 \
    --set resources.requests.cpu=250m \
    --set resources.requests.memory=512Mi \
    --set resources.limits.cpu=1000m \
    --set resources.limits.memory=2Gi \
    --wait \
    --timeout 10m

# Wait for deployment
echo "⏳ Waiting for deployment to be ready..."
kubectl wait --for=condition=available --timeout=300s \
    deployment/x0tta6bl4 -n $NAMESPACE

# Check health
echo "🏥 Checking health..."
sleep 5
kubectl port-forward -n $NAMESPACE svc/x0tta6bl4 8000:8000 &
PF_PID=$!
sleep 3

if curl -f http://localhost:8000/health >/dev/null 2>&1; then
    echo "✅ Health check passed"
    curl -s http://localhost:8000/health | jq '.' || curl -s http://localhost:8000/health
else
    echo "❌ Health check failed"
    kill $PF_PID 2>/dev/null || true
    exit 1
fi

kill $PF_PID 2>/dev/null || true

# Show status
echo ""
echo "📊 Deployment Status:"
kubectl get pods -n $NAMESPACE
kubectl get svc -n $NAMESPACE

echo ""
echo "✅ Staging deployment complete!"
echo "   Namespace: $NAMESPACE"
echo "   Version: $VERSION"

