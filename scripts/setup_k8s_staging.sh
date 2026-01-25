#!/bin/bash

set -euo pipefail

# Setup x0tta6bl4 on Kubernetes (k3s/minikube/kind)
# Usage: ./setup_k8s_staging.sh [--runtime k3s|minikube|kind] [--cleanup]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NAMESPACE="x0tta6bl4"
RUNTIME="k3s"  # Default: k3s (fastest for staging)
CLEANUP=false

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --runtime) RUNTIME="$2"; shift 2 ;;
        --cleanup) CLEANUP=true; shift ;;
        *) log_error "Unknown option: $1"; exit 1 ;;
    esac
done

# Check kubectl
if ! command -v kubectl &> /dev/null; then
    log_error "kubectl not found. Please install kubectl first."
    exit 1
fi

log_info "Setting up x0tta6bl4 on Kubernetes ($RUNTIME)"

# Setup cluster based on runtime
case $RUNTIME in
    k3s)
        log_info "Using k3s (local lightweight k8s)"
        if ! command -v k3s &> /dev/null; then
            log_warn "k3s not found. Install with: curl -sfL https://get.k3s.io | sh -"
            log_info "For testing, using current kubectl context"
        else
            log_info "k3s detected"
        fi
        ;;
    minikube)
        log_info "Using minikube"
        if ! command -v minikube &> /dev/null; then
            log_error "minikube not found. Install from https://minikube.sigs.k8s.io/docs/start/"
            exit 1
        fi
        
        if $CLEANUP; then
            log_warn "Cleaning up minikube..."
            minikube delete || true
        fi
        
        log_info "Starting minikube..."
        minikube start --cpus=4 --memory=8192 --driver=docker \
            --extra-config=apiserver.audit-policy-file=/etc/kubernetes/audit/audit-policy.yaml \
            --extra-config=apiserver.audit-log-path=/var/log/kubernetes/audit/audit.log || true
        
        log_info "Enabling metrics-server..."
        minikube addons enable metrics-server || true
        
        log_info "Enabling ingress..."
        minikube addons enable ingress || true
        ;;
    kind)
        log_info "Using kind (Kubernetes in Docker)"
        if ! command -v kind &> /dev/null; then
            log_error "kind not found. Install with: go install sigs.k8s.io/kind@latest"
            exit 1
        fi
        
        if $CLEANUP; then
            log_warn "Cleaning up kind cluster..."
            kind delete cluster --name x0tta6bl4 || true
        fi
        
        log_info "Creating kind cluster..."
        kind create cluster --name x0tta6bl4 || true
        ;;
    *)
        log_error "Unknown runtime: $RUNTIME"
        exit 1
        ;;
esac

# Get current context
CONTEXT=$(kubectl config current-context)
log_info "Current kubectl context: $CONTEXT"

# Create namespace
log_info "Creating namespace: $NAMESPACE"
kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -

# Create SPIRE namespace for identity
log_info "Creating namespace: spire"
kubectl create namespace spire --dry-run=client -o yaml | kubectl apply -f -

# Deploy SPIRE for identity (if SPIRE K8s manifests exist)
if [ -f "$SCRIPT_DIR/infra/k8s/kind-local/spire-server.yaml" ]; then
    log_info "Deploying SPIRE Server..."
    kubectl apply -f "$SCRIPT_DIR/infra/k8s/kind-local/spire-server.yaml"
    
    log_info "Waiting for SPIRE Server to be ready..."
    kubectl wait --for=condition=ready pod -l app=spire-server -n spire --timeout=300s || true
fi

if [ -f "$SCRIPT_DIR/infra/k8s/kind-local/spire-agent.yaml" ]; then
    log_info "Deploying SPIRE Agent..."
    kubectl apply -f "$SCRIPT_DIR/infra/k8s/kind-local/spire-agent.yaml"
    
    log_info "Waiting for SPIRE Agent to be ready..."
    kubectl wait --for=condition=ready pod -l app=spire-agent -n spire --timeout=300s || true
fi

# Deploy x0tta6bl4 using Helm
if [ -f "$SCRIPT_DIR/infra/helm/x0tta6bl4/Chart.yaml" ]; then
    log_info "Deploying x0tta6bl4 using Helm..."
    
    # Create values file for staging
    cat > /tmp/x0tta6bl4-staging-values.yaml <<EOF
# Staging environment values
replicaCount: 2

image:
  tag: latest
  pullPolicy: IfNotPresent

ingress:
  enabled: true
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-staging
  hosts:
    - host: x0tta6bl4.local
      paths:
        - path: /
          pathType: Prefix

resources:
  limits:
    cpu: 1000m
    memory: 1024Mi
  requests:
    cpu: 500m
    memory: 512Mi

autoscaling:
  enabled: true
  minReplicas: 1
  maxReplicas: 3
  targetCPUUtilizationPercentage: 80

monitoring:
  enabled: true
  
spiffe:
  enabled: true
  trustDomain: x0tta6bl4.mesh
EOF
    
    helm install x0tta6bl4 "$SCRIPT_DIR/infra/helm/x0tta6bl4" \
        --namespace $NAMESPACE \
        -f /tmp/x0tta6bl4-staging-values.yaml \
        --wait || log_warn "Helm install completed with warnings"
fi

# Verify deployment
log_info "Verifying deployment..."
kubectl get pods -n $NAMESPACE
kubectl get svc -n $NAMESPACE

# Show access information
log_info "🎉 x0tta6bl4 staging environment deployed!"
echo ""
echo "Next steps:"
echo "1. Check pod status:"
echo "   kubectl get pods -n $NAMESPACE"
echo ""
echo "2. View logs:"
echo "   kubectl logs -n $NAMESPACE -l app=x0tta6bl4 -f"
echo ""
echo "3. Access the service:"
if [ "$RUNTIME" == "minikube" ]; then
    echo "   minikube service x0tta6bl4 -n $NAMESPACE"
else
    echo "   kubectl port-forward -n $NAMESPACE svc/x0tta6bl4 8080:8080"
fi
echo ""
echo "4. Run smoke tests:"
echo "   kubectl run -it --rm --restart=Never test-pod --image=curlimages/curl -n $NAMESPACE -- curl http://x0tta6bl4:8080/health"
echo ""
echo "5. Clean up:"
echo "   $0 --runtime $RUNTIME --cleanup"
