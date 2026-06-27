#!/bin/bash
# Auto-deployment script for staging environment
# Waits for Docker build completion and deploys to staging

set -e

VERSION="3.4.0"
NAMESPACE="x0tta6bl4-staging"
CHART_PATH="./helm/x0tta6bl4"
BUILD_PID="193112"  # Current Docker build process ID

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     Auto Staging Deployment Script                          ║"
echo "║     Version: $VERSION                                      ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Function to check if Docker build is still running
check_docker_build() {
    if ps -p $BUILD_PID > /dev/null 2>&1; then
        echo "🐳 Docker build still running (PID: $BUILD_PID)..."
        
        # Show latest build progress
        LATEST_LOG=$(find /home/x0ttta6bl4/.gemini/tmp -name "docker_build_v3.4.0_*.log" -type f -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)
        if [ -f "$LATEST_LOG" ]; then
            echo "📊 Latest build progress:"
            tail -3 "$LATEST_LOG" | grep -E "(transferring|Step|=>"
        fi
        
        return 0
    else
        echo "✅ Docker build completed!"
        return 1
    fi
}

# Function to wait for Docker build completion
wait_for_docker_build() {
    echo "⏳ Waiting for Docker build to complete..."
    
    while check_docker_build; do
        sleep 30
        echo "⏰ $(date '+%H:%M:%S') - Still building..."
    done
    
    echo ""
    echo "🔍 Verifying Docker image..."
    if docker images x0tta6bl4:$VERSION | grep -q $VERSION; then
        echo "✅ Docker image x0tta6bl4:$VERSION found!"
        docker images x0tta6bl4:$VERSION
    else
        echo "❌ Docker image not found. Build may have failed."
        echo "📋 Checking build logs..."
        LATEST_LOG=$(find /home/x0ttta6bl4/.gemini/tmp -name "docker_build_v3.4.0_*.log" -type f -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)
        if [ -f "$LATEST_LOG" ]; then
            echo "📄 Last 20 lines of build log:"
            tail -20 "$LATEST_LOG"
        fi
        exit 1
    fi
}

# Function to load image into kind cluster
load_image_to_kind() {
    echo ""
    echo "📦 Loading Docker image into kind cluster..."
    
    if kind load docker-image x0tta6bl4:$VERSION --name x0tta6bl4-staging; then
        echo "✅ Image loaded into kind cluster successfully!"
    else
        echo "❌ Failed to load image into kind cluster"
        exit 1
    fi
}

# Function to deploy with Helm
deploy_with_helm() {
    echo ""
    echo "🚀 Deploying x0tta6bl4 to staging with Helm..."
    
    # Create namespace if not exists
    kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -
    
    # Deploy using values-staging.yaml
    if helm upgrade --install x0tta6bl4-staging $CHART_PATH \
        --namespace $NAMESPACE \
        --create-namespace \
        --values $CHART_PATH/values-staging.yaml \
        --wait \
        --timeout 15m; then
        echo "✅ Helm deployment successful!"
    else
        echo "❌ Helm deployment failed"
        exit 1
    fi
}

# Function to verify deployment
verify_deployment() {
    echo ""
    echo "🔍 Verifying deployment..."
    
    # Wait for deployment to be ready
    echo "⏳ Waiting for deployment to be ready..."
    if kubectl wait --for=condition=available --timeout=300s \
        deployment/x0tta6bl4-staging -n $NAMESPACE; then
        echo "✅ Deployment is ready!"
    else
        echo "❌ Deployment failed to become ready"
        exit 1
    fi
    
    # Show pod status
    echo ""
    echo "📊 Pod Status:"
    kubectl get pods -n $NAMESPACE -o wide
    
    # Show service status
    echo ""
    echo "🌐 Service Status:"
    kubectl get services -n $NAMESPACE
    
    # Health check
    echo ""
    echo "🏥 Performing health check..."
    kubectl port-forward -n $NAMESPACE svc/x0tta6bl4-staging 8080:8080 &
    PF_PID=$!
    sleep 5
    
    if curl -f http://localhost:8080/health >/dev/null 2>&1; then
        echo "✅ Health check passed!"
        echo "📋 Health response:"
        curl -s http://localhost:8080/health | jq '.' 2>/dev/null || curl -s http://localhost:8080/health
    else
        echo "❌ Health check failed"
        echo "📋 Checking pod logs..."
        kubectl logs -n $NAMESPACE -l app.kubernetes.io/name=x0tta6bl4 --tail=20
    fi
    
    kill $PF_PID 2>/dev/null || true
}

# Function to show next steps
show_next_steps() {
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║     🎉 DEPLOYMENT COMPLETE!                                 ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""
    echo "📋 Deployment Summary:"
    echo "   • Namespace: $NAMESPACE"
    echo "   • Version: $VERSION"
    echo "   • Replicas: 2"
    echo ""
    echo "🔗 Access URLs:"
    echo "   • Health: http://localhost:8080/health (with port-forward)"
    echo "   • API: http://localhost:8080/api/v1/"
    echo ""
    echo "📝 Next Steps:"
    echo "   1. Set up monitoring (Prometheus/Grafana)"
    echo "   2. Run P0 component validation (Jan 8-14)"
    echo "   3. Configure alerting"
    echo "   4. Begin beta testing preparation"
    echo ""
    echo "🔧 Useful Commands:"
    echo "   • Port-forward: kubectl port-forward -n $NAMESPACE svc/x0tta6bl4-staging 8080:8080"
    echo "   • Logs: kubectl logs -n $NAMESPACE -l app.kubernetes.io/name=x0tta6bl4 -f"
    echo "   • Exec: kubectl exec -n $NAMESPACE -l app.kubernetes.io/name=x0tta6bl4 -- bash"
}

# Main execution
main() {
    echo "🚀 Starting auto-deployment process..."
    
    # Check prerequisites
    command -v kubectl >/dev/null 2>&1 || { echo "❌ kubectl not found"; exit 1; }
    command -v helm >/dev/null 2>&1 || { echo "❌ helm not found"; exit 1; }
    command -v kind >/dev/null 2>&1 || { echo "❌ kind not found"; exit 1; }
    
    # Check cluster access
    if ! kubectl cluster-info >/dev/null 2>&1; then
        echo "❌ Cannot connect to Kubernetes cluster"
        exit 1
    fi
    
    echo "✅ Prerequisites checked"
    echo ""
    
    # Execute deployment steps
    wait_for_docker_build
    load_image_to_kind
    deploy_with_helm
    verify_deployment
    show_next_steps
}

# Run main function
main
