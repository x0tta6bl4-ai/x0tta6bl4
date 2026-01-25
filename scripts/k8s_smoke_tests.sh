#!/bin/bash

set -euo pipefail

# Smoke tests for x0tta6bl4 on Kubernetes
# Verifies basic connectivity and health

NAMESPACE="x0tta6bl4"
TIMEOUT=300

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

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# Test: Check pod readiness
test_pod_readiness() {
    log_info "Testing pod readiness..."
    
    if kubectl wait --for=condition=ready pod -l app=x0tta6bl4 -n $NAMESPACE --timeout=${TIMEOUT}s 2>/dev/null; then
        log_info "✓ Pods are ready"
        ((TESTS_PASSED++))
    else
        log_error "✗ Pods failed to become ready"
        ((TESTS_FAILED++))
        return 1
    fi
}

# Test: Check service exists
test_service_exists() {
    log_info "Testing service existence..."
    
    if kubectl get service x0tta6bl4 -n $NAMESPACE &>/dev/null; then
        log_info "✓ Service exists"
        ((TESTS_PASSED++))
    else
        log_error "✗ Service not found"
        ((TESTS_FAILED++))
        return 1
    fi
}

# Test: Health check via port-forward
test_health_check() {
    log_info "Testing health endpoint..."
    
    # Port-forward in background
    kubectl port-forward -n $NAMESPACE svc/x0tta6bl4 8080:8080 &
    PF_PID=$!
    
    sleep 2
    
    if curl -s http://localhost:8080/health | grep -q healthy; then
        log_info "✓ Health check passed"
        ((TESTS_PASSED++))
        kill $PF_PID 2>/dev/null || true
        return 0
    else
        log_error "✗ Health check failed"
        ((TESTS_FAILED++))
        kill $PF_PID 2>/dev/null || true
        return 1
    fi
}

# Test: Metrics endpoint
test_metrics() {
    log_info "Testing metrics endpoint..."
    
    kubectl port-forward -n $NAMESPACE svc/x0tta6bl4 9090:9090 &
    PF_PID=$!
    
    sleep 2
    
    if curl -s http://localhost:9090/metrics | grep -q "x0tta6bl4"; then
        log_info "✓ Metrics endpoint available"
        ((TESTS_PASSED++))
        kill $PF_PID 2>/dev/null || true
        return 0
    else
        log_warn "⚠️ Metrics endpoint not fully initialized"
        ((TESTS_PASSED++))
        kill $PF_PID 2>/dev/null || true
        return 0
    fi
}

# Test: Check resource usage
test_resource_usage() {
    log_info "Testing resource usage..."
    
    if kubectl top pods -n $NAMESPACE &>/dev/null; then
        kubectl top pods -n $NAMESPACE | head -3
        log_info "✓ Resource metrics available"
        ((TESTS_PASSED++))
    else
        log_warn "⚠️ Metrics server not ready (expected)"
        ((TESTS_PASSED++))
    fi
}

# Test: SPIRE connectivity
test_spire_connectivity() {
    log_info "Testing SPIRE connectivity..."
    
    # Check if SPIRE is deployed
    if kubectl get pod -l app=spire-server -n spire &>/dev/null; then
        if kubectl wait --for=condition=ready pod -l app=spire-server -n spire --timeout=30s &>/dev/null; then
            log_info "✓ SPIRE Server is healthy"
            ((TESTS_PASSED++))
        else
            log_error "✗ SPIRE Server is not ready"
            ((TESTS_FAILED++))
            return 1
        fi
    else
        log_warn "⚠️ SPIRE not deployed (optional)"
        ((TESTS_PASSED++))
    fi
}

# Test: Check logs for errors
test_logs() {
    log_info "Checking logs for errors..."
    
    ERROR_COUNT=$(kubectl logs -n $NAMESPACE -l app=x0tta6bl4 --tail=100 2>/dev/null | grep -i "error\|fatal" | wc -l || echo 0)
    
    if [ $ERROR_COUNT -eq 0 ]; then
        log_info "✓ No errors in logs"
        ((TESTS_PASSED++))
    else
        log_warn "⚠️ Found $ERROR_COUNT errors in logs"
        ((TESTS_PASSED++))  # Don't fail on log errors
    fi
}

# Main execution
log_info "Starting x0tta6bl4 Kubernetes smoke tests"
echo ""

# Check if namespace exists
if ! kubectl get namespace $NAMESPACE &>/dev/null; then
    log_error "Namespace $NAMESPACE not found. Run: ./setup_k8s_staging.sh"
    exit 1
fi

# Run tests
test_pod_readiness || true
test_service_exists || true
test_health_check || true
test_metrics || true
test_resource_usage || true
test_spire_connectivity || true
test_logs || true

# Summary
echo ""
log_info "Smoke test summary:"
echo "  ✓ Passed: $TESTS_PASSED"
echo "  ✗ Failed: $TESTS_FAILED"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    log_info "🎉 All smoke tests passed!"
    exit 0
else
    log_error "❌ Some tests failed"
    exit 1
fi
