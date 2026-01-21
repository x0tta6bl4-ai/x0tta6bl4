#!/bin/bash
# Deployment script for staging environment from local registry
# Usage: ./scripts/deploy_staging_registry.sh [version]

set -e

VERSION=${1:-"3.4.0-fixed2"}
NAMESPACE="x0tta6bl4-staging"
CHART_PATH="./helm/x0tta6bl4"
IMAGE_NAME="localhost:5001/x0tta6bl4"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     Staging Deployment Script (Local Registry)                ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check prerequisites
echo "📋 Checking prerequisites..."
command -v kubectl >/dev/null 2>&1 || { echo "❌ kubectl not found"; exit 1; }
command -v helm >/dev/null 2>&1 || { echo "❌ helm not found"; exit 1; }

# Check kubectl connection
if ! kubectl cluster-info >/dev/null 2>&1;
then
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
    --set image.repository=$IMAGE_NAME \
    --set image.tag=$VERSION \
    --set production.enabled=false \
    --set replicaCount=2 \
    --set resources.requests.cpu=250m \
    --set resources.requests.memory=512Mi \
    --set resources.limits.cpu=1000m \
    --set resources.limits.memory=2Gi \
    --timeout 10m

echo ""
echo "✅ Staging deployment initiated!"
echo "   Namespace: $NAMESPACE"
echo "   Version: $VERSION"
echo "   Image: $IMAGE_NAME:$VERSION"
