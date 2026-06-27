#!/bin/bash
# Rollback procedures for staging deployment

set -e

NAMESPACE="x0tta6bl4-staging"
RELEASE_NAME="x0tta6bl4-staging"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     Staging Rollback Procedures                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Function to get current deployment status
check_deployment_status() {
    echo "🔍 Checking current deployment status..."
    kubectl get pods -n $NAMESPACE -l app.kubernetes.io/name=x0tta6bl4
    kubectl get deployment -n $NAMESPACE $RELEASE_NAME
}

# Function to perform Helm rollback
helm_rollback() {
    echo "🔄 Performing Helm rollback..."
    
    # Get revision history
    echo "📜 Available revisions:"
    helm history $RELEASE_NAME -n $NAMESPACE
    
    # Rollback to previous revision
    echo "⏪ Rolling back to previous revision..."
    helm rollback $RELEASE_NAME -n $NAMESPACE
    
    echo "⏳ Waiting for rollback to complete..."
    kubectl rollout status deployment/$RELEASE_NAME -n $NAMESPACE --timeout=300s
}

# Function to perform emergency rollback (delete and redeploy)
emergency_rollback() {
    echo "🚨 Performing emergency rollback..."
    
    # Delete current deployment
    echo "🗑️ Deleting current deployment..."
    helm uninstall $RELEASE_NAME -n $NAMESPACE || true
    kubectl delete namespace $NAMESPACE || true
    
    # Recreate namespace
    echo "📦 Recreating namespace..."
    kubectl create namespace $NAMESPACE
    
    # Redeploy with known good configuration
    echo "🚀 Redeploying with known good configuration..."
    helm upgrade --install $RELEASE_NAME ./helm/x0tta6bl4 \
        -f helm/x0tta6bl4/values-staging.yaml \
        -n $NAMESPACE \
        --wait \
        --timeout=10m
}

# Function to verify rollback success
verify_rollback() {
    echo "✅ Verifying rollback success..."
    
    # Check pod status
    kubectl get pods -n $NAMESPACE -l app.kubernetes.io/name=x0tta6bl4
    
    # Check health endpoint
    echo "🏥 Checking health endpoint..."
    kubectl port-forward -n $NAMESPACE svc/$RELEASE_NAME 8080:8080 &
    PF_PID=$!
    sleep 5
    
    if curl -f http://localhost:8080/health > /dev/null 2>&1; then
        echo "✅ Health check passed"
    else
        echo "❌ Health check failed"
    fi
    
    # Kill port-forward
    kill $PF_PID 2>/dev/null || true
}

# Function to cleanup resources
cleanup_resources() {
    echo "🧹 Cleaning up resources..."
    
    # Delete failed pods
    kubectl delete pods -n $NAMESPACE -l app.kubernetes.io/name=x0tta6bl4 --field-selector=status.phase=Failed || true
    
    # Reset Helm release
    helm uninstall $RELEASE_NAME -n $NAMESPACE || true
}

# Main rollback flow
main() {
    case "${1:-help}" in
        "check")
            check_deployment_status
            ;;
        "helm")
            check_deployment_status
            helm_rollback
            verify_rollback
            ;;
        "emergency")
            check_deployment_status
            emergency_rollback
            verify_rollback
            ;;
        "cleanup")
            cleanup_resources
            ;;
        "help"|*)
            echo "Usage: $0 {check|helm|emergency|cleanup|help}"
            echo ""
            echo "Commands:"
            echo "  check     - Check current deployment status"
            echo "  helm      - Perform Helm rollback to previous revision"
            echo "  emergency - Emergency rollback (delete and redeploy)"
            echo "  cleanup   - Cleanup failed resources"
            echo "  help      - Show this help message"
            exit 1
            ;;
    esac
}

main "$@"
