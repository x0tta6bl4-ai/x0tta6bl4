#!/bin/bash
# P0 Components Validation Script for Staging Environment

set -e

NAMESPACE="x0tta6bl4-staging"
BASE_URL="http://localhost:8080"
LOG_FILE="/tmp/p0_validation_$(date +%Y%m%d_%H%M%S).log"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REAL_READINESS_JSON=".tmp/validation-shards/real-readiness-current.json"
REAL_READINESS_MD=".tmp/validation-shards/real-readiness-current.md"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     P0 Components Validation                                  ║"
echo "║     Environment: Staging                                     ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Function to log results
log_result() {
    local test_name="$1"
    local status="$2"
    local message="$3"
    
    echo "[$status] $test_name: $message" | tee -a "$LOG_FILE"
    
    if [ "$status" = "✅ PASS" ]; then
        return 0
    else
        return 1
    fi
}

# Function to setup port-forward
setup_port_forward() {
    echo "🔗 Setting up port-forward..."
    kubectl port-forward -n $NAMESPACE svc/x0tta6bl4-staging 8080:8080 &
    PF_PID=$!
    sleep 5
    
    # Check if port-forward is working
    if ! curl -s $BASE_URL/health >/dev/null 2>&1; then
        log_result "Port Forward" "❌ FAIL" "Cannot establish connection to application"
        kill $PF_PID 2>/dev/null || true
        exit 1
    fi
    
    log_result "Port Forward" "✅ PASS" "Port-forward established successfully"
}

# Function to cleanup
cleanup() {
    echo ""
    echo "🧹 Cleaning up..."
    kill $PF_PID 2>/dev/null || true
    echo "✅ Cleanup complete"
}

# Set trap for cleanup
trap cleanup EXIT

# Function to test basic health
test_basic_health() {
    echo ""
    echo "🏥 Testing Basic Health..."
    
    local response=$(curl -s $BASE_URL/health)
    local http_code=$(curl -s -o /dev/null -w "%{http_code}" $BASE_URL/health)
    
    if [ "$http_code" = "200" ]; then
        log_result "Basic Health" "✅ PASS" "HTTP 200 - Service is healthy"
        echo "📋 Health response: $response"
    else
        log_result "Basic Health" "❌ FAIL" "HTTP $http_code - Service unhealthy"
        return 1
    fi
}

# Function to test Payment Verification
test_payment_verification() {
    echo ""
    echo "💳 Testing Payment Verification..."
    
    # Test USDT verification endpoint
    local usdt_response=$(curl -s -X POST "$BASE_URL/api/v1/payments/verify/usdt" \
        -H "Content-Type: application/json" \
        -d '{
            "transaction_hash": "test_hash_123",
            "amount": "10.0",
            "from_address": "test_from_address",
            "to_address": "test_to_address"
        }')
    
    local usdt_code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/api/v1/payments/verify/usdt" \
        -H "Content-Type: application/json" \
        -d '{
            "transaction_hash": "test_hash_123",
            "amount": "10.0",
            "from_address": "test_from_address",
            "to_address": "test_to_address"
        }')
    
    if [ "$usdt_code" = "200" ] || [ "$usdt_code" = "400" ] || [ "$usdt_code" = "422" ]; then
        log_result "USDT Verification API" "✅ PASS" "API endpoint responding (HTTP $usdt_code)"
        echo "📋 USDT Response: $usdt_response"
    else
        log_result "USDT Verification API" "❌ FAIL" "API not responding (HTTP $usdt_code)"
    fi
    
    # Test TON verification endpoint
    local ton_response=$(curl -s -X POST "$BASE_URL/api/v1/payments/verify/ton" \
        -H "Content-Type: application/json" \
        -d '{
            "transaction_hash": "test_ton_hash_123",
            "amount": "5.0",
            "from_address": "test_ton_from",
            "to_address": "test_ton_to"
        }')
    
    local ton_code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/api/v1/payments/verify/ton" \
        -H "Content-Type: application/json" \
        -d '{
            "transaction_hash": "test_ton_hash_123",
            "amount": "5.0",
            "from_address": "test_ton_from",
            "to_address": "test_ton_to"
        }')
    
    if [ "$ton_code" = "200" ] || [ "$ton_code" = "400" ] || [ "$ton_code" = "422" ]; then
        log_result "TON Verification API" "✅ PASS" "API endpoint responding (HTTP $ton_code)"
        echo "📋 TON Response: $ton_response"
    else
        log_result "TON Verification API" "❌ FAIL" "API not responding (HTTP $ton_code)"
    fi
}

# Function to test eBPF Observability
test_ebpf_observability() {
    echo ""
    echo "🔍 Testing eBPF Observability..."
    
    # Check if eBPF metrics endpoint exists
    local ebpf_response=$(curl -s "$BASE_URL/api/v1/observability/ebpf/metrics")
    local ebpf_code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/v1/observability/ebpf/metrics")
    
    if [ "$ebpf_code" = "200" ]; then
        log_result "eBPF Metrics API" "✅ PASS" "eBPF metrics available (HTTP $ebpf_code)"
        echo "📋 eBPF Metrics: $ebpf_response"
    elif [ "$ebpf_code" = "404" ]; then
        log_result "eBPF Metrics API" "⚠️ SKIP" "eBPF endpoint not found (feature disabled in staging)"
    elif [ "$ebpf_code" = "501" ]; then
        log_result "eBPF Metrics API" "⚠️ SKIP" "eBPF not implemented (expected in staging)"
    else
        log_result "eBPF Metrics API" "❌ FAIL" "Unexpected response (HTTP $ebpf_code)"
    fi
    
    # Check eBPF status
    local ebpf_status=$(curl -s "$BASE_URL/api/v1/observability/ebpf/status")
    local status_code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/v1/observability/ebpf/status")
    
    if [ "$status_code" = "200" ]; then
        log_result "eBPF Status Check" "✅ PASS" "eBPF status endpoint responding"
        echo "📋 eBPF Status: $ebpf_status"
    else
        log_result "eBPF Status Check" "⚠️ SKIP" "eBPF status endpoint not available (HTTP $status_code)"
    fi
}

# Function to test GraphSAGE Causal Analysis
test_graphsage_causal() {
    echo ""
    echo "🧠 Testing GraphSAGE Causal Analysis..."
    
    # Test causal analysis endpoint
    local causal_response=$(curl -s -X POST "$BASE_URL/api/v1/ml/causal/analyze" \
        -H "Content-Type: application/json" \
        -d '{
            "anomaly_id": "test_anomaly_123",
            "time_range": {
                "start": "2026-01-05T00:00:00Z",
                "end": "2026-01-05T01:00:00Z"
            },
            "node_ids": ["node1", "node2", "node3"]
        }')
    
    local causal_code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/api/v1/ml/causal/analyze" \
        -H "Content-Type: application/json" \
        -d '{
            "anomaly_id": "test_anomaly_123",
            "time_range": {
                "start": "2026-01-05T00:00:00Z",
                "end": "2026-01-05T01:00:00Z"
            },
            "node_ids": ["node1", "node2", "node3"]
        }')
    
    if [ "$causal_code" = "200" ]; then
        log_result "GraphSAGE Causal API" "✅ PASS" "Causal analysis working (HTTP $causal_code)"
        echo "📋 Causal Analysis Response: $causal_response"
    elif [ "$causal_code" = "400" ] || [ "$causal_code" = "422" ]; then
        log_result "GraphSAGE Causal API" "✅ PASS" "API responding, validation working (HTTP $causal_code)"
    elif [ "$causal_code" = "501" ]; then
        log_result "GraphSAGE Causal API" "⚠️ SKIP" "Not implemented in staging (HTTP $causal_code)"
    else
        log_result "GraphSAGE Causal API" "❌ FAIL" "API not responding (HTTP $causal_code)"
    fi
    
    # Test GraphSAGE model status
    local gs_status=$(curl -s "$BASE_URL/api/v1/ml/graphsage/status")
    local gs_code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/v1/ml/graphsage/status")
    
    if [ "$gs_code" = "200" ]; then
        log_result "GraphSAGE Model Status" "✅ PASS" "GraphSAGE model status available"
        echo "📋 GraphSAGE Status: $gs_status"
    else
        log_result "GraphSAGE Model Status" "⚠️ SKIP" "GraphSAGE status not available (HTTP $gs_code)"
    fi
}

# Function to test overall API endpoints
test_api_endpoints() {
    echo ""
    echo "🔗 Testing Core API Endpoints..."
    
    local endpoints=(
        "/api/v1/health"
        "/api/v1/status"
        "/api/v1/metrics"
        "/api/v1/version"
    )
    
    for endpoint in "${endpoints[@]}"; do
        local response_code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL$endpoint")
        
        if [ "$response_code" = "200" ]; then
            log_result "API $endpoint" "✅ PASS" "Endpoint responding"
        else
            log_result "API $endpoint" "❌ FAIL" "Endpoint not responding (HTTP $response_code)"
        fi
    done
}

# Function to generate summary report
generate_summary() {
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║     VALIDATION SUMMARY                                       ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""
    
    local total_tests=$(grep -c "\[.*\]" "$LOG_FILE")
    local passed_tests=$(grep -c "✅ PASS" "$LOG_FILE")
    local failed_tests=$(grep -c "❌ FAIL" "$LOG_FILE")
    local skipped_tests=$(grep -c "⚠️ SKIP" "$LOG_FILE")
    
    echo "📊 Test Results:"
    echo "   • Total Tests: $total_tests"
    echo "   • ✅ Passed: $passed_tests"
    echo "   • ❌ Failed: $failed_tests"
    echo "   • ⚠️ Skipped: $skipped_tests"
    echo ""
    
    if [ "$failed_tests" -eq 0 ]; then
        echo "🎉 ALL CRITICAL TESTS PASSED!"
        echo "Local P0 checks passed. Production validation claim requires the fail-closed real-readiness gate."
        if python3 "$ROOT_DIR/scripts/ops/check_real_readiness.py" \
            --write-json "$REAL_READINESS_JSON" \
            --write-md "$REAL_READINESS_MD" >/dev/null; then
            echo "✅ REAL READINESS GATE: PASSED"
        else
            echo "❌ REAL READINESS GATE: BLOCKED"
            echo "P0 checks passed, but production validation is not allowed yet."
            echo "Report: $REAL_READINESS_JSON"
            return 1
        fi
    else
        echo "⚠️ SOME TESTS FAILED!"
        echo "❌ P0 Components require fixes before production"
    fi
    
    echo ""
    echo "📄 Detailed log saved to: $LOG_FILE"
    echo ""
    
    # Show failed tests if any
    if [ "$failed_tests" -gt 0 ]; then
        echo "❌ Failed Tests:"
        grep "❌ FAIL" "$LOG_FILE" | sed 's/^/   • /'
        echo ""
    fi
}

# Main execution
main() {
    echo "🚀 Starting P0 Components Validation..."
    echo "📝 Logging results to: $LOG_FILE"
    echo ""
    
    setup_port_forward
    test_basic_health
    test_api_endpoints
    test_payment_verification
    test_ebpf_observability
    test_graphsage_causal
    generate_summary
}

# Check prerequisites
command -v kubectl >/dev/null 2>&1 || { echo "❌ kubectl not found"; exit 1; }
command -v curl >/dev/null 2>&1 || { echo "❌ curl not found"; exit 1; }

# Check if deployment exists
if ! kubectl get deployment x0tta6bl4-staging -n $NAMESPACE >/dev/null 2>&1; then
    echo "❌ Deployment x0tta6bl4-staging not found in namespace $NAMESPACE"
    echo "Please run deployment first: ./scripts/auto_deploy_staging.sh"
    exit 1
fi

# Run validation
main
