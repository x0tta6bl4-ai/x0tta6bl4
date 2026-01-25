#!/bin/bash
# Cluster validation script
# Validates Kubernetes cluster readiness for x0tta6bl4

set -e

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     Cluster Validation Script                                ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check prerequisites
command -v kubectl >/dev/null 2>&1 || { echo "❌ kubectl not found"; exit 1; }

# Check cluster connection
echo "🔌 Checking cluster connection..."
if ! kubectl cluster-info >/dev/null 2>&1; then
    echo "❌ Cannot connect to Kubernetes cluster"
    exit 1
fi
echo "✅ Cluster connection OK"
echo ""

# Check cluster version
echo "📋 Cluster Information:"
kubectl version --short
echo ""

# Check nodes
echo "🖥️  Node Status:"
kubectl get nodes -o wide
echo ""

# Check if nodes are ready
READY_NODES=$(kubectl get nodes --no-headers | grep -c " Ready " || echo "0")
TOTAL_NODES=$(kubectl get nodes --no-headers | wc -l || echo "0")

if [ "$READY_NODES" -lt "$TOTAL_NODES" ]; then
    echo "⚠️  Warning: Not all nodes are ready ($READY_NODES/$TOTAL_NODES)"
else
    echo "✅ All nodes ready ($READY_NODES/$TOTAL_NODES)"
fi
echo ""

# Check namespaces
echo "📦 Namespaces:"
kubectl get namespaces
echo ""

# Check if required namespaces exist
REQUIRED_NS=("x0tta6bl4" "monitoring" "kube-system")
for ns in "${REQUIRED_NS[@]}"; do
    if kubectl get namespace "$ns" >/dev/null 2>&1; then
        echo "✅ Namespace '$ns' exists"
    else
        echo "⚠️  Namespace '$ns' does not exist (will be created during deployment)"
    fi
done
echo ""

# Check storage classes
echo "💾 Storage Classes:"
kubectl get storageclass || echo "No storage classes found"
echo ""

# Check if default storage class exists
if kubectl get storageclass | grep -q "default"; then
    echo "✅ Default storage class exists"
else
    echo "⚠️  Warning: No default storage class found"
fi
echo ""

# Check metrics server
echo "📊 Metrics Server:"
if kubectl get deployment metrics-server -n kube-system >/dev/null 2>&1; then
    echo "✅ Metrics server is available"
else
    echo "⚠️  Warning: Metrics server not found (HPA may not work)"
fi
echo ""

# Check ingress controller
echo "🌐 Ingress Controller:"
if kubectl get pods -A | grep -q "ingress"; then
    echo "✅ Ingress controller found"
else
    echo "⚠️  Warning: Ingress controller not found"
fi
echo ""

# Check CNI
echo "🔗 CNI Plugin:"
if kubectl get pods -n kube-system | grep -q "cni\|flannel\|calico\|weave"; then
    echo "✅ CNI plugin found"
else
    echo "⚠️  Warning: CNI plugin not detected"
fi
echo ""

# Check resource quotas
echo "📊 Resource Quotas:"
kubectl get resourcequota -A 2>/dev/null | head -5 || echo "No resource quotas found"
echo ""

# Check network policies support
echo "🛡️  Network Policies:"
if kubectl get networkpolicy -A >/dev/null 2>&1; then
    echo "✅ Network policies are supported"
else
    echo "⚠️  Warning: Network policies may not be supported"
fi
echo ""

# Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Validation Summary:"
echo "   Ready Nodes: $READY_NODES/$TOTAL_NODES"
echo "   Cluster: $(kubectl cluster-info | grep -oP 'https://\K[^:]+' || echo 'unknown')"
echo ""
echo "✅ Cluster validation complete!"

