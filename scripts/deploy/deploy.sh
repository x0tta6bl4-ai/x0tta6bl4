#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

DEPLOYMENT_NAME="${DEPLOYMENT_NAME:-x0tta6bl4}"
NAMESPACE="${NAMESPACE:-x0tta6bl4-prod}"
STRATEGY="${STRATEGY:-rolling}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
DOCKER_REGISTRY="${DOCKER_REGISTRY:-docker.io}"
ENABLE_GITOPS="${ENABLE_GITOPS:-true}"

log_info() {
    echo "ℹ️  $*"
}

log_success() {
    echo "✅ $*"
}

log_error() {
    echo "❌ $*" >&2
}

log_warning() {
    echo "⚠️  $*"
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl not found"
        return 1
    fi
    
    if ! command -v helm &> /dev/null; then
        log_error "helm not found"
        return 1
    fi
    
    if [[ "$ENABLE_GITOPS" == "true" ]] && ! command -v argocd &> /dev/null; then
        log_warning "argocd not found, GitOps will be skipped"
        ENABLE_GITOPS="false"
    fi
    
    log_success "Prerequisites check passed"
    return 0
}

create_namespace() {
    log_info "Ensuring namespace exists: $NAMESPACE"
    
    if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
        log_info "Creating namespace: $NAMESPACE"
        kubectl create namespace "$NAMESPACE"
        
        kubectl label namespace "$NAMESPACE" \
            app.kubernetes.io/name=x0tta6bl4 \
            environment=production \
            --overwrite
    fi
    
    log_success "Namespace ready"
}

configure_secrets() {
    log_info "Configuring secrets..."
    
    if [[ -n "${POSTGRES_PASSWORD:-}" ]]; then
        kubectl create secret generic postgres-credentials \
            --from-literal=POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
            --from-literal=POSTGRES_APP_PASSWORD="${POSTGRES_APP_PASSWORD:-}" \
            -n "$NAMESPACE" \
            --dry-run=client -o yaml | kubectl apply -f -
    fi
    
    if [[ -n "${DOCKER_USERNAME:-}" ]] && [[ -n "${DOCKER_PASSWORD:-}" ]]; then
        kubectl create secret docker-registry regcred \
            --docker-server="$DOCKER_REGISTRY" \
            --docker-username="$DOCKER_USERNAME" \
            --docker-password="$DOCKER_PASSWORD" \
            -n "$NAMESPACE" \
            --dry-run=client -o yaml | kubectl apply -f -
    fi
    
    log_success "Secrets configured"
}

deploy_with_helm() {
    log_info "Deploying with Helm (strategy: $STRATEGY)..."
    
    local helm_opts=(
        "upgrade"
        "--install"
        "$DEPLOYMENT_NAME"
        "$PROJECT_ROOT/helm/x0tta6bl4"
        "-n"
        "$NAMESPACE"
        "-f"
        "$PROJECT_ROOT/helm/x0tta6bl4/values-production.yaml"
        "--set"
        "image.tag=$IMAGE_TAG"
        "--set"
        "image.repository=$DOCKER_REGISTRY/$DEPLOYMENT_NAME"
        "--timeout"
        "10m"
        "--wait"
    )
    
    case "$STRATEGY" in
        rolling)
            helm_opts+=("--atomic")
            ;;
        canary)
            helm_opts+=(
                "--set"
                "strategy=canary"
                "--set"
                "canary.enabled=true"
            )
            ;;
        bluegreen)
            helm_opts+=(
                "--set"
                "strategy=bluegreen"
                "--set"
                "bluegreen.enabled=true"
            )
            ;;
    esac
    
    helm "${helm_opts[@]}"
    
    log_success "Helm deployment completed"
}

wait_for_rollout() {
    log_info "Waiting for rollout to complete..."
    
    kubectl rollout status deployment/"$DEPLOYMENT_NAME" \
        -n "$NAMESPACE" \
        --timeout=5m
    
    log_success "Rollout completed"
}

validate_health() {
    log_info "Validating deployment health..."
    
    local max_retries=30
    local retry_count=0
    
    while [[ $retry_count -lt $max_retries ]]; do
        local ready_pods=$(kubectl get deployment "$DEPLOYMENT_NAME" \
            -n "$NAMESPACE" \
            -o jsonpath='{.status.readyReplicas}')
        local desired_pods=$(kubectl get deployment "$DEPLOYMENT_NAME" \
            -n "$NAMESPACE" \
            -o jsonpath='{.spec.replicas}')
        
        if [[ "$ready_pods" == "$desired_pods" ]] && [[ "$ready_pods" -gt 0 ]]; then
            log_success "All pods are healthy ($ready_pods/$desired_pods)"
            return 0
        fi
        
        log_info "Waiting for pods to be ready ($ready_pods/$desired_pods)..."
        sleep 5
        ((retry_count++))
    done
    
    log_error "Health validation timeout"
    return 1
}

run_smoke_tests() {
    log_info "Running smoke tests..."
    
    local pod_name=$(kubectl get pods -n "$NAMESPACE" \
        -l app.kubernetes.io/name="$DEPLOYMENT_NAME" \
        -o jsonpath='{.items[0].metadata.name}')
    
    if [[ -z "$pod_name" ]]; then
        log_error "No pods found for smoke tests"
        return 1
    fi
    
    log_info "Testing pod: $pod_name"
    
    kubectl exec "$pod_name" -n "$NAMESPACE" -- \
        curl -s http://localhost:8000/health/ready || {
        log_error "Health check failed"
        return 1
    }
    
    log_success "Smoke tests passed"
    return 0
}

sync_gitops() {
    if [[ "$ENABLE_GITOPS" != "true" ]]; then
        log_info "GitOps disabled"
        return 0
    fi
    
    log_info "Syncing ArgoCD application..."
    
    local argocd_app="${ARGOCD_APP_NAME:-x0tta6bl4}"
    
    argocd app sync "$argocd_app" \
        --prune \
        --self-heal \
        --timeout 5m || {
        log_warning "GitOps sync failed (non-fatal)"
        return 0
    }
    
    log_success "GitOps sync completed"
    return 0
}

rollback_deployment() {
    log_warning "Rolling back deployment..."
    
    kubectl rollout undo deployment/"$DEPLOYMENT_NAME" \
        -n "$NAMESPACE"
    
    kubectl rollout status deployment/"$DEPLOYMENT_NAME" \
        -n "$NAMESPACE" \
        --timeout=5m
    
    log_success "Rollback completed"
}

handle_error() {
    log_error "Deployment failed"
    
    if [[ "${ENABLE_ROLLBACK:-true}" == "true" ]]; then
        rollback_deployment
    fi
    
    exit 1
}

main() {
    log_info "🚀 Starting production deployment"
    log_info "   Deployment: $DEPLOYMENT_NAME"
    log_info "   Namespace: $NAMESPACE"
    log_info "   Strategy: $STRATEGY"
    log_info "   Image tag: $IMAGE_TAG"
    log_info ""
    
    trap handle_error ERR
    
    check_prerequisites
    create_namespace
    configure_secrets
    deploy_with_helm
    wait_for_rollout
    
    if ! validate_health; then
        log_error "Health validation failed"
        handle_error
    fi
    
    if ! run_smoke_tests; then
        log_error "Smoke tests failed"
        handle_error
    fi
    
    sync_gitops
    
    log_success "✅ Deployment completed successfully"
    
    log_info ""
    log_info "Deployment Status:"
    kubectl get deployment "$DEPLOYMENT_NAME" -n "$NAMESPACE"
    log_info ""
    log_info "Pod Status:"
    kubectl get pods -l app.kubernetes.io/name="$DEPLOYMENT_NAME" -n "$NAMESPACE"
}

main "$@"
