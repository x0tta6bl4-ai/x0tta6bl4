#!/bin/bash
# Validate Kubernetes deployment for x0tta6bl4
# Tests deployment manifests, health checks, and production readiness

set -e

echo "🔍 Validating Kubernetes Deployment..."

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl not found. Install kubectl to validate deployment."
    exit 1
fi

# Validate YAML syntax
echo "📋 Validating YAML syntax..."
kubectl apply --dry-run=client -f deployment/kubernetes/deployment.yaml
kubectl apply --dry-run=client -f deployment/kubernetes/service.yaml
kubectl apply --dry-run=client -f deployment/kubernetes/configmap.yaml
kubectl apply --dry-run=client -f deployment/kubernetes/ingress.yaml

# Check for required fields
echo "✅ Checking required fields..."

# Check deployment has health checks
if ! grep -q "livenessProbe" deployment/kubernetes/deployment.yaml; then
    echo "❌ Missing livenessProbe in deployment"
    exit 1
fi

if ! grep -q "readinessProbe" deployment/kubernetes/deployment.yaml; then
    echo "❌ Missing readinessProbe in deployment"
    exit 1
fi

# Check service has correct selector
if ! grep -q "app: x0tta6bl4" deployment/kubernetes/service.yaml; then
    echo "❌ Service selector mismatch"
    exit 1
fi

# Check ingress has TLS
if ! grep -q "tls:" deployment/kubernetes/ingress.yaml; then
    echo "⚠️  Ingress missing TLS configuration"
fi

# Check resource limits
if ! grep -q "resources:" deployment/kubernetes/deployment.yaml; then
    echo "⚠️  Deployment missing resource limits"
fi

echo "✅ Kubernetes deployment validation complete"

