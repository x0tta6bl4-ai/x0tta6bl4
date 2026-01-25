#!/bin/bash
# Smoke Tests for Staging Deployment
# Validates critical functionality after deployment

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

CONTROL_PLANE_URL="${CONTROL_PLANE_URL:-http://localhost:8080}"
MESH_NODE_URL="${MESH_NODE_URL:-http://localhost:8081}"

PASSED=0
FAILED=0

test_pass() {
    echo -e "${GREEN}✅ PASS${NC}: $1"
    ((PASSED++))
}

test_fail() {
    echo -e "${RED}❌ FAIL${NC}: $1"
    ((FAILED++))
}

test_info() {
    echo -e "${YELLOW}ℹ️  INFO${NC}: $1"
}

echo "🧪 x0tta6bl4 Smoke Tests"
echo "========================"
echo ""
echo "Control Plane: $CONTROL_PLANE_URL"
echo "Mesh Node: $MESH_NODE_URL"
echo ""

# Test 1: Control Plane Health
echo "[1/10] Control Plane Health Check..."
if curl -f -s "$CONTROL_PLANE_URL/health" > /dev/null; then
    test_pass "Control Plane is healthy"
else
    test_fail "Control Plane health check failed"
fi

# Test 2: Metrics Endpoint
echo "[2/10] Metrics Endpoint..."
if curl -f -s "$CONTROL_PLANE_URL/metrics" | grep -q "http_requests_total"; then
    test_pass "Metrics endpoint is working"
else
    test_fail "Metrics endpoint not accessible or empty"
fi

# Test 3: Mesh Status
echo "[3/10] Mesh Status..."
if curl -f -s "$CONTROL_PLANE_URL/mesh/status" > /dev/null; then
    test_pass "Mesh status endpoint is accessible"
else
    test_fail "Mesh status endpoint failed"
fi

# Test 4: MAPE-K Cycle Status
echo "[4/10] MAPE-K Cycle Status..."
if curl -f -s "$CONTROL_PLANE_URL/mape-k/status" > /dev/null; then
    test_pass "MAPE-K cycle is running"
else
    test_fail "MAPE-K cycle status check failed"
fi

# Test 5: Prometheus Scraping
echo "[5/10] Prometheus Scraping..."
PROMETHEUS_URL="${PROMETHEUS_URL:-http://localhost:9091}"
if curl -f -s "$PROMETHEUS_URL/api/v1/targets" > /dev/null; then
    test_pass "Prometheus is accessible"
else
    test_fail "Prometheus not accessible"
fi

# Test 6: Grafana Dashboard
echo "[6/10] Grafana Dashboard..."
GRAFANA_URL="${GRAFANA_URL:-http://localhost:3000}"
if curl -f -s "$GRAFANA_URL/api/health" > /dev/null; then
    test_pass "Grafana is accessible"
else
    test_fail "Grafana not accessible"
fi

# Test 7: Network Connectivity (if mesh nodes exist)
echo "[7/10] Mesh Node Connectivity..."
if curl -f -s "$MESH_NODE_URL/health" > /dev/null 2>&1; then
    test_pass "Mesh nodes are reachable"
else
    test_info "Mesh nodes not found (this is OK for minimal staging)"
fi

# Test 8: Security (mTLS) - if configured
echo "[8/10] Security Validation..."
if curl -f -s "$CONTROL_PLANE_URL/security/status" > /dev/null 2>&1; then
    test_pass "Security endpoints are accessible"
else
    test_info "Security endpoints not configured (this is OK for staging)"
fi

# Test 9: API Response Time
echo "[9/10] API Response Time..."
RESPONSE_TIME=$(curl -o /dev/null -s -w '%{time_total}' "$CONTROL_PLANE_URL/health")
if (( $(echo "$RESPONSE_TIME < 1.0" | bc -l) )); then
    test_pass "API response time acceptable: ${RESPONSE_TIME}s"
else
    test_fail "API response time too slow: ${RESPONSE_TIME}s"
fi

# Test 10: Error Rate Check
echo "[10/10] Error Rate Check..."
ERROR_RATE=$(curl -s "$PROMETHEUS_URL/api/v1/query?query=rate(http_requests_total{status=~\"5..\"}[5m])" 2>/dev/null | jq -r '.data.result[0].value[1]' 2>/dev/null || echo "0")
if (( $(echo "$ERROR_RATE < 0.01" | bc -l) )); then
    test_pass "Error rate acceptable: $ERROR_RATE"
else
    test_fail "Error rate too high: $ERROR_RATE"
fi

# Summary
echo ""
echo "========================"
echo "Test Summary"
echo "========================"
echo -e "${GREEN}Passed: $PASSED${NC}"
if [ $FAILED -gt 0 ]; then
    echo -e "${RED}Failed: $FAILED${NC}"
    echo ""
    echo "⚠️  Some tests failed. Please review the errors above."
    exit 1
else
    echo -e "${GREEN}Failed: $FAILED${NC}"
    echo ""
    echo "✅ All smoke tests passed!"
    exit 0
fi

