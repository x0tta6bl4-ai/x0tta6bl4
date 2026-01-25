#!/bin/bash
# Production Deployment Script
# Дата: 2026-01-07
# Версия: 3.4.0-fixed2

set -euo pipefail

# Configuration
NAMESPACE="${NAMESPACE:-x0tta6bl4-production}"
RELEASE_NAME="${RELEASE_NAME:-x0tta6bl4}"
HELM_CHART="./helm/x0tta6bl4"
VALUES_FILE="${VALUES_FILE:-./helm/x0tta6bl4/values-production.yaml}"
IMAGE_TAG="${IMAGE_TAG:-3.4.0-fixed2}"
DRY_RUN="${DRY_RUN:-false}"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# Pre-flight checks
preflight_checks() {
    log "Running pre-flight checks..."
    
    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        error "kubectl not found"
        exit 1
    fi
    
    # Check helm
    if ! command -v helm &> /dev/null; then
        error "helm not found"
        exit 1
    fi
    
    # Check cluster connectivity
    if ! kubectl cluster-info &> /dev/null; then
        error "Cannot connect to Kubernetes cluster"
        exit 1
    fi
    
    # Check values file
    if [ ! -f "$VALUES_FILE" ]; then
        error "Values file not found: $VALUES_FILE"
        exit 1
    fi
    
    # Check namespace
    if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
        warn "Namespace $NAMESPACE does not exist, will be created"
    fi
    
    log "✅ Pre-flight checks passed"
}

# Create namespace
create_namespace() {
    if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
        log "Creating namespace: $NAMESPACE"
        kubectl create namespace "$NAMESPACE"
        
        # Add labels
        kubectl label namespace "$NAMESPACE" \
          environment=production \
          app=x0tta6bl4 \
          managed-by=helm
    else
        log "Namespace $NAMESPACE already exists"
    fi
}

# Deploy with Helm
deploy_helm() {
    log "Deploying with Helm..."
    
    local helm_cmd="helm upgrade --install $RELEASE_NAME $HELM_CHART"
    helm_cmd="$helm_cmd -f $VALUES_FILE"
    helm_cmd="$helm_cmd --set image.tag=$IMAGE_TAG"
    helm_cmd="$helm_cmd --namespace $NAMESPACE"
    helm_cmd="$helm_cmd --create-namespace"
    
    if [ "$DRY_RUN" = "true" ]; then
        helm_cmd="$helm_cmd --dry-run --debug"
        info "DRY RUN MODE - no changes will be made"
    fi
    
    log "Executing: $helm_cmd"
    eval "$helm_cmd"
    
    if [ "$DRY_RUN" != "true" ]; then
        log "✅ Helm deployment completed"
    fi
}

# Wait for deployment
wait_for_deployment() {
    if [ "$DRY_RUN" = "true" ]; then
        return
    fi
    
    log "Waiting for deployment to be ready..."
    
    kubectl wait --for=condition=available \
      --timeout=300s \
      deployment/$RELEASE_NAME \
      -n "$NAMESPACE" || {
        error "Deployment failed to become ready"
        kubectl describe deployment/$RELEASE_NAME -n "$NAMESPACE"
        exit 1
    }
    
    log "✅ Deployment is ready"
}

# Verify health
verify_health() {
    if [ "$DRY_RUN" = "true" ]; then
        return
    fi
    
    log "Verifying health..."
    
    # Get service URL
    local service_url
    if kubectl get svc "$RELEASE_NAME" -n "$NAMESPACE" &> /dev/null; then
        local service_type=$(kubectl get svc "$RELEASE_NAME" -n "$NAMESPACE" -o jsonpath='{.spec.type}')
        
        if [ "$service_type" = "LoadBalancer" ]; then
            service_url=$(kubectl get svc "$RELEASE_NAME" -n "$NAMESPACE" -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
            if [ -z "$service_url" ]; then
                service_url=$(kubectl get svc "$RELEASE_NAME" -n "$NAMESPACE" -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
            fi
        elif [ "$service_type" = "NodePort" ]; then
            local node_port=$(kubectl get svc "$RELEASE_NAME" -n "$NAMESPACE" -o jsonpath='{.spec.ports[0].nodePort}')
            service_url="localhost:$node_port"
        else
            # Port-forward for ClusterIP
            info "Service is ClusterIP, using port-forward for health check"
            kubectl port-forward -n "$NAMESPACE" svc/$RELEASE_NAME 8080:8080 &
            local pf_pid=$!
            sleep 5
            service_url="localhost:8080"
        fi
        
        # Health check
        local max_attempts=30
        local attempt=0
        
        while [ $attempt -lt $max_attempts ]; do
            if curl -sf "http://$service_url/health" > /dev/null 2>&1; then
                log "✅ Health check passed"
                if [ -n "${pf_pid:-}" ]; then
                    kill $pf_pid 2>/dev/null || true
                fi
                return 0
            fi
            
            attempt=$((attempt + 1))
            sleep 5
        done
        
        if [ -n "${pf_pid:-}" ]; then
            kill $pf_pid 2>/dev/null || true
        fi
        
        warn "Health check failed after $max_attempts attempts"
        return 1
    else
        warn "Service not found, skipping health check"
    fi
}

# Display deployment info
display_info() {
    if [ "$DRY_RUN" = "true" ]; then
        return
    fi
    
    log "Deployment Information:"
    echo ""
    echo "Namespace: $NAMESPACE"
    echo "Release: $RELEASE_NAME"
    echo "Image Tag: $IMAGE_TAG"
    echo ""
    
    info "Pods:"
    kubectl get pods -n "$NAMESPACE" -l app=$RELEASE_NAME
    
    echo ""
    info "Services:"
    kubectl get svc -n "$NAMESPACE" -l app=$RELEASE_NAME
    
    echo ""
    info "Deployment Status:"
    kubectl get deployment -n "$NAMESPACE" $RELEASE_NAME
}

# Main execution
main() {
    log "╔══════════════════════════════════════════════════════════════╗"
    log "║     Production Deployment Script                             ║"
    log "╚══════════════════════════════════════════════════════════════╝"
    echo ""
    
    info "Configuration:"
    echo "  Namespace: $NAMESPACE"
    echo "  Release: $RELEASE_NAME"
    echo "  Image Tag: $IMAGE_TAG"
    echo "  Values File: $VALUES_FILE"
    echo "  Dry Run: $DRY_RUN"
    echo ""
    
    preflight_checks
    create_namespace
    deploy_helm
    wait_for_deployment
    verify_health
    display_info
    
    log "╔══════════════════════════════════════════════════════════════╗"
    log "║     Deployment Completed Successfully                        ║"
    log "╚══════════════════════════════════════════════════════════════╝"
}

# Run if executed directly
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    main "$@"
fi
