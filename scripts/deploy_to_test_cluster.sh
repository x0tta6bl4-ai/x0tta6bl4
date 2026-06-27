#!/bin/bash
# Deploy x0tta6bl4 to test Kubernetes cluster
# Supports minikube, kind, and existing clusters

set -e

CLUSTER_TYPE="${1:-auto}"

echo "🚀 Deploying x0tta6bl4 to test cluster..."

# Detect cluster type
if [ "$CLUSTER_TYPE" = "auto" ]; then
    if kubectl cluster-info &> /dev/null; then
        echo "✅ Using existing Kubernetes cluster"
        CLUSTER_TYPE="existing"
    elif minikube status &> /dev/null; then
        echo "✅ Using minikube cluster"
        CLUSTER_TYPE="minikube"
        minikube start || true
    elif kind get clusters &> /dev/null; then
        echo "✅ Using kind cluster"
        CLUSTER_TYPE="kind"
        if ! kind get clusters | grep -q "x0tta6bl4"; then
            echo "Creating kind cluster..."
            kind create cluster --name x0tta6bl4
        fi
    else
        echo "❌ No Kubernetes cluster found"
        echo "Please start minikube, kind, or connect to existing cluster"
        exit 1
    fi
fi

# Apply manifests
echo "📋 Applying Kubernetes manifests..."

# ConfigMap first
kubectl apply -f deployment/kubernetes/configmap.yaml

# Deployment
kubectl apply -f deployment/kubernetes/deployment.yaml

# Service
kubectl apply -f deployment/kubernetes/service.yaml

# Wait for deployment
echo "⏳ Waiting for deployment to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/x0tta6bl4 || true

# Check status
echo "📊 Deployment status:"
kubectl get deployment x0tta6bl4
kubectl get pods -l app=x0tta6bl4

# Check health
echo "🏥 Checking health endpoints..."
POD_NAME=$(kubectl get pods -l app=x0tta6bl4 -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
if [ -n "$POD_NAME" ]; then
    echo "Testing health endpoint on pod $POD_NAME..."
    kubectl exec "$POD_NAME" -- curl -s http://localhost:8080/health || echo "⚠️  Health check failed (pod may still be starting)"
fi

echo "✅ Deployment complete"

