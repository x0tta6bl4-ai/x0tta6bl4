#!/bin/bash
set -e

VERSION="1.0"
CLUSTER_NAME="x0tta6bl4-staging"
NAMESPACE_STAGING="x0tta6bl4-staging"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║     K3s Staging Environment Setup                             ║"
echo "║     Version: $VERSION                                        ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

check_prerequisites() {
    echo "🔍 Checking prerequisites..."
    
    MISSING_TOOLS=()
    
    for tool in kubectl helm kustomize; do
        if ! command -v $tool &> /dev/null; then
            MISSING_TOOLS+=("$tool")
        fi
    done
    
    if [ ${#MISSING_TOOLS[@]} -gt 0 ]; then
        echo "❌ Missing tools: ${MISSING_TOOLS[*]}"
        echo ""
        echo "Install instructions:"
        echo "  kubectl: https://kubernetes.io/docs/tasks/tools/"
        echo "  helm:    https://helm.sh/docs/intro/install/"
        echo "  kustomize: https://kustomize.io/"
        exit 1
    fi
    
    echo "✅ All prerequisites found"
}

verify_cluster_access() {
    echo ""
    echo "🔐 Verifying cluster access..."
    
    if kubectl cluster-info &>/dev/null; then
        echo "✅ Cluster accessible"
        CLUSTER_VERSION=$(kubectl version --short 2>/dev/null | grep Server | awk '{print $3}')
        echo "   Version: $CLUSTER_VERSION"
    else
        echo "❌ Cannot connect to Kubernetes cluster"
        echo "   Ensure kubeconfig is configured correctly"
        exit 1
    fi
}

create_namespaces() {
    echo ""
    echo "📦 Creating namespaces..."
    
    for ns in $NAMESPACE_STAGING monitoring spire; do
        if kubectl get namespace $ns &>/dev/null; then
            echo "   ℹ️  Namespace $ns already exists"
        else
            kubectl create namespace $ns
            kubectl label namespace $ns environment=staging
            echo "   ✓ Created namespace $ns"
        fi
    done
}

apply_manifests_kustomize() {
    echo ""
    echo "🚀 Applying Kubernetes manifests (kustomize)..."
    
    if [ ! -f "infra/k8s/overlays/staging/kustomization.yaml" ]; then
        echo "❌ Kustomization file not found: infra/k8s/overlays/staging/kustomization.yaml"
        exit 1
    fi
    
    if kubectl apply -k infra/k8s/overlays/staging/; then
        echo "✅ Manifests applied successfully"
    else
        echo "❌ Failed to apply manifests"
        exit 1
    fi
}

apply_spire_manifests() {
    echo ""
    echo "🔐 Applying SPIRE manifests..."
    
    if [ -f "infra/k8s/kind-local/spire-server.yaml" ]; then
        kubectl apply -f infra/k8s/kind-local/spire-server.yaml
        echo "✓ SPIRE server deployed"
    fi
    
    if [ -f "infra/k8s/kind-local/spire-agent.yaml" ]; then
        kubectl apply -f infra/k8s/kind-local/spire-agent.yaml
        echo "✓ SPIRE agent deployed"
    fi
}

verify_deployment() {
    echo ""
    echo "🔍 Verifying deployment..."
    
    echo "⏳ Waiting for deployment..."
    if kubectl wait --for=condition=available --timeout=120s \
        deployment/staging-x0tta6bl4 -n $NAMESPACE_STAGING 2>/dev/null; then
        echo "✅ Deployment ready"
    else
        echo "⚠️  Deployment not ready yet (this is normal for first deployment)"
        echo "   Check status with: kubectl get pods -n $NAMESPACE_STAGING"
    fi
    
    echo ""
    echo "📊 Deployment status:"
    kubectl get pods -n $NAMESPACE_STAGING -o wide
    
    echo ""
    echo "🌐 Services:"
    kubectl get svc -n $NAMESPACE_STAGING
}

setup_port_forwarding() {
    echo ""
    echo "🔗 Setting up port forwarding (optional)..."
    echo ""
    echo "To access the application:"
    echo "  kubectl port-forward -n $NAMESPACE_STAGING svc/staging-x0tta6bl4 8000:8000 &"
    echo ""
    echo "To access Grafana:"
    echo "  kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80 &"
    echo ""
    echo "To access Prometheus:"
    echo "  kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090 &"
}

show_summary() {
    echo ""
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║     ✅ K3s Staging Environment Setup Complete!                 ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""
    echo "📋 Summary:"
    echo "   Cluster: $CLUSTER_NAME"
    echo "   Namespace: $NAMESPACE_STAGING"
    echo "   Monitoring: monitoring"
    echo "   SPIRE: spire"
    echo ""
    echo "📝 Next steps:"
    echo "   1. Deploy monitoring stack: make monitoring-stack"
    echo "   2. Run smoke tests: pytest tests/integration/test_k8s_smoke.py"
    echo "   3. Check pod status: kubectl get pods -n $NAMESPACE_STAGING"
    echo ""
    echo "🔧 Useful commands:"
    echo "   Logs: kubectl logs -n $NAMESPACE_STAGING -l app.kubernetes.io/name=x0tta6bl4 -f"
    echo "   Shell: kubectl exec -n $NAMESPACE_STAGING -it deployment/staging-x0tta6bl4 -- bash"
    echo "   Events: kubectl describe deployment staging-x0tta6bl4 -n $NAMESPACE_STAGING"
}

main() {
    check_prerequisites
    verify_cluster_access
    create_namespaces
    apply_manifests_kustomize
    apply_spire_manifests
    verify_deployment
    setup_port_forwarding
    show_summary
}

main
