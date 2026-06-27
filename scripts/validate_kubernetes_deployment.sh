#!/bin/bash
# Local Kubernetes manifest validation for x0tta6bl4.
# This is not production readiness proof.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "🔍 Validating local Kubernetes manifests..."
echo "Claim boundary: this checks manifest syntax and local required fields only."
echo "It does not prove live cluster rollout, customer traffic, external DPI bypass,"
echo "settlement finality, production SLOs, or production readiness."

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl not found. Install kubectl to validate local manifests."
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

echo "✅ Local Kubernetes manifest validation complete"
echo "For a production claim, use the fail-closed real-readiness gate:"
echo "python3 scripts/ops/check_real_readiness.py"
