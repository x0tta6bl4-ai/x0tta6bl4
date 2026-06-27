#!/bin/bash
# Quick Demo Deployment Script for x0tta6bl4
# Deploys a minimal demo environment to existing Kubernetes cluster

set -e

echo "🚀 Deploying x0tta6bl4 Demo Environment..."
echo ""

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl not found. Please install kubectl first."
    exit 1
fi

# Check if cluster is accessible
if ! kubectl cluster-info &> /dev/null; then
    echo "❌ Cannot connect to Kubernetes cluster."
    echo "Please start minikube, kind, or connect to existing cluster"
    exit 1
fi

echo "✅ Kubernetes cluster accessible"
kubectl cluster-info | head -1
echo ""

# Create namespace if it doesn't exist
echo "📦 Creating namespace (if needed)..."
kubectl create namespace x0tta6bl4-demo --dry-run=client -o yaml | kubectl apply -f - || true

# Apply ConfigMap
echo "📋 Applying ConfigMap..."
kubectl apply -f deployment/kubernetes/configmap.yaml -n x0tta6bl4-demo || \
kubectl apply -f deployment/kubernetes/configmap.yaml

# Apply demo deployment
echo "📋 Applying Demo Deployment..."
if [ -f "deployment/kubernetes/deployment-demo.yaml" ]; then
    kubectl apply -f deployment/kubernetes/deployment-demo.yaml
else
    echo "⚠️  deployment-demo.yaml not found, using standard deployment..."
    kubectl apply -f deployment/kubernetes/deployment.yaml
fi

# Apply service
echo "📋 Applying Service..."
kubectl apply -f deployment/kubernetes/service.yaml

# Wait for deployment
echo ""
echo "⏳ Waiting for deployment to be ready..."
kubectl wait --for=condition=available --timeout=120s deployment/x0tta6bl4-demo 2>/dev/null || \
kubectl wait --for=condition=available --timeout=120s deployment/x0tta6bl4 2>/dev/null || true

# Check status
echo ""
echo "📊 Deployment Status:"
echo "===================="
kubectl get deployment -l app=x0tta6bl4
echo ""
kubectl get pods -l app=x0tta6bl4
echo ""
kubectl get svc -l app=x0tta6bl4

# Port-forward instructions
echo ""
echo "✅ Demo deployment complete!"
echo ""
echo "🌐 To access the demo:"
echo "   kubectl port-forward svc/x0tta6bl4 8080:80"
echo ""
echo "   Then open: http://localhost:8080"
echo ""
echo "📝 Check logs:"
echo "   kubectl logs -l app=x0tta6bl4 --tail=50"
echo ""
