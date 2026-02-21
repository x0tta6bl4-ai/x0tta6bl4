#!/bin/bash
# MaaS Kubernetes Staging Deployment Script
# ==========================================
# This script deploys MaaS to a Kubernetes staging environment.

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="${NAMESPACE:-maas-staging}"
RELEASE_NAME="${RELEASE_NAME:-maas}"
HELM_TIMEOUT="${HELM_TIMEOUT:-10m}"
VALUES_FILE="${VALUES_FILE:-deploy/helm/maas/values-staging.yaml}"

# Stripe configuration (required)
STRIPE_SECRET_KEY="${STRIPE_SECRET_KEY:-}"
STRIPE_WEBHOOK_SECRET="${STRIPE_WEBHOOK_SECRET:-}"

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed"
        exit 1
    fi
    
    # Check helm
    if ! command -v helm &> /dev/null; then
        log_error "helm is not installed"
        exit 1
    fi
    
    # Check cluster connection
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

create_namespace() {
    log_info "Creating namespace: $NAMESPACE"
    
    if kubectl get namespace "$NAMESPACE" &> /dev/null; then
        log_warning "Namespace $NAMESPACE already exists"
    else
        kubectl create namespace "$NAMESPACE"
        kubectl label namespace "$NAMESPACE" environment=staging --overwrite
        log_success "Namespace $NAMESPACE created"
    fi
}

setup_secrets() {
    log_info "Setting up secrets..."
    
    # Check if Stripe keys are provided
    if [[ -z "$STRIPE_SECRET_KEY" ]]; then
        log_warning "STRIPE_SECRET_KEY not set. Using placeholder."
        STRIPE_SECRET_KEY="sk_test_placeholder"
    fi
    
    if [[ -z "$STRIPE_WEBHOOK_SECRET" ]]; then
        log_warning "STRIPE_WEBHOOK_SECRET not set. Using placeholder."
        STRIPE_WEBHOOK_SECRET="whsec_placeholder"
    fi
    
    log_success "Secrets configuration ready"
}

add_helm_repos() {
    log_info "Adding Helm repositories..."
    
    helm repo add bitnami https://charts.bitnami.com/bitnami 2>/dev/null || true
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts 2>/dev/null || true
    helm repo add grafana https://grafana.github.io/helm-charts 2>/dev/null || true
    helm repo update
    
    log_success "Helm repositories updated"
}

deploy_with_helm() {
    log_info "Deploying MaaS with Helm..."
    
    local helm_args=(
        "--namespace" "$NAMESPACE"
        "--timeout" "$HELM_TIMEOUT"
        "--values" "$VALUES_FILE"
        "--set" "stripe.secretKey=$STRIPE_SECRET_KEY"
        "--set" "stripe.webhookSecret=$STRIPE_WEBHOOK_SECRET"
    )
    
    # Check if release exists
    if helm status "$RELEASE_NAME" --namespace "$NAMESPACE" &> /dev/null; then
        log_info "Upgrading existing release: $RELEASE_NAME"
        helm upgrade "$RELEASE_NAME" deploy/helm/maas "${helm_args[@]}"
    else
        log_info "Installing new release: $RELEASE_NAME"
        helm install "$RELEASE_NAME" deploy/helm/maas "${helm_args[@]}"
    fi
    
    log_success "Helm deployment completed"
}

wait_for_deployment() {
    log_info "Waiting for deployment to be ready..."
    
    kubectl rollout status deployment/"$RELEASE_NAME-api" \
        --namespace "$NAMESPACE" \
        --timeout=300s
    
    log_success "Deployment is ready"
}

verify_deployment() {
    log_info "Verifying deployment..."
    
    # Check pods
    local ready_pods
    ready_pods=$(kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/name=maas \
        -o jsonpath='{.items[*].status.conditions[?(@.type=="Ready")].status}' \
        | tr ' ' '\n' | grep -c "True" || true)
    
    log_info "Ready pods: $ready_pods"
    
    # Check services
    kubectl get services -n "$NAMESPACE"
    
    # Check ingress
    kubectl get ingress -n "$NAMESPACE"
    
    log_success "Deployment verification completed"
}

get_access_info() {
    log_info "Access information:"
    
    # Get API URL
    local api_url
    api_url=$(kubectl get ingress -n "$NAMESPACE" \
        -o jsonpath='{.items[0].spec.rules[0].host}' 2>/dev/null || echo "Not available")
    
    echo ""
    echo "========================================"
    echo "MaaS Staging Deployment Complete!"
    echo "========================================"
    echo ""
    echo "API URL: https://$api_url"
    echo ""
    echo "Useful commands:"
    echo "  kubectl get pods -n $NAMESPACE"
    echo "  kubectl logs -f deployment/maas-api -n $NAMESPACE"
    echo "  kubectl port-forward svc/maas-api 8080:8080 -n $NAMESPACE"
    echo ""
}

main() {
    log_info "Starting MaaS staging deployment..."
    echo ""
    
    check_prerequisites
    create_namespace
    setup_secrets
    add_helm_repos
    deploy_with_helm
    wait_for_deployment
    verify_deployment
    get_access_info
    
    log_success "Deployment completed successfully!"
}

# Run main function
main "$@"
