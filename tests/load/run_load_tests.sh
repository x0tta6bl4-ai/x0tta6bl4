#!/bin/bash
# MaaS Load Testing Runner
# ========================
# Run k6 load tests against staging environment

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
BASE_URL="${BASE_URL:-https://api.staging.maas-x0tta6bl4.local}"
API_KEY="${API_KEY:-}"
TEST_DIR="tests/load"
RESULTS_DIR="load-test-results"

# Test types
TEST_TYPE="${1:-all}"

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
    
    # Check k6
    if ! command -v k6 &> /dev/null; then
        log_error "k6 is not installed"
        log_info "Install k6: https://k6.io/docs/getting-started/installation/"
        exit 1
    fi
    
    # Check API key
    if [[ -z "$API_KEY" ]]; then
        log_warning "API_KEY not set. Some tests may fail."
    fi
    
    # Create results directory
    mkdir -p "$RESULTS_DIR"
    
    log_success "Prerequisites check passed"
}

run_smoke_test() {
    log_info "Running smoke test..."
    
    k6 run \
        --env BASE_URL="$BASE_URL" \
        --env API_KEY="$API_KEY" \
        --out json="$RESULTS_DIR/smoke-test.json" \
        --summary-export="$RESULTS_DIR/smoke-summary.json" \
        --tag test_type=smoke \
        "$TEST_DIR/maas_load_test.js" \
        --scenario smoke_test
    
    log_success "Smoke test completed"
}

run_load_test() {
    log_info "Running load test..."
    
    k6 run \
        --env BASE_URL="$BASE_URL" \
        --env API_KEY="$API_KEY" \
        --out json="$RESULTS_DIR/load-test.json" \
        --summary-export="$RESULTS_DIR/load-summary.json" \
        --tag test_type=load \
        "$TEST_DIR/maas_load_test.js" \
        --scenario load_test
    
    log_success "Load test completed"
}

run_stress_test() {
    log_info "Running stress test..."
    
    k6 run \
        --env BASE_URL="$BASE_URL" \
        --env API_KEY="$API_KEY" \
        --out json="$RESULTS_DIR/stress-test.json" \
        --summary-export="$RESULTS_DIR/stress-summary.json" \
        --tag test_type=stress \
        "$TEST_DIR/maas_load_test.js" \
        --scenario stress_test
    
    log_success "Stress test completed"
}

run_spike_test() {
    log_info "Running spike test..."
    
    k6 run \
        --env BASE_URL="$BASE_URL" \
        --env API_KEY="$API_KEY" \
        --out json="$RESULTS_DIR/spike-test.json" \
        --summary-export="$RESULTS_DIR/spike-summary.json" \
        --tag test_type=spike \
        "$TEST_DIR/maas_load_test.js" \
        --scenario spike_test
    
    log_success "Spike test completed"
}

run_soak_test() {
    log_info "Running soak test (30 minutes)..."
    
    k6 run \
        --env BASE_URL="$BASE_URL" \
        --env API_KEY="$API_KEY" \
        --out json="$RESULTS_DIR/soak-test.json" \
        --summary-export="$RESULTS_DIR/soak-summary.json" \
        --tag test_type=soak \
        "$TEST_DIR/maas_load_test.js" \
        --scenario soak_test
    
    log_success "Soak test completed"
}

run_all_tests() {
    log_info "Running all load tests..."
    
    # Run each test type
    run_smoke_test
    echo ""
    
    run_load_test
    echo ""
    
    run_stress_test
    echo ""
    
    run_spike_test
    echo ""
    
    # Skip soak test by default (takes 30 minutes)
    log_warning "Soak test skipped (use 'soak' to run separately)"
}

generate_report() {
    log_info "Generating test report..."
    
    python3 << 'PYTHON_EOF'
import json
import os
from datetime import datetime

results_dir = os.environ.get('RESULTS_DIR', 'load-test-results')
report_file = os.path.join(results_dir, 'test-report.md')

summaries = []
for filename in os.listdir(results_dir):
    if filename.endswith('-summary.json'):
        filepath = os.path.join(results_dir, filename)
        with open(filepath) as f:
            summary = json.load(f)
            test_type = filename.replace('-summary.json', '')
            summaries.append((test_type, summary))

# Generate report
report = f"""# MaaS Load Test Report

Generated: {datetime.now().isoformat()}

## Summary

| Test Type | Requests | Failed | Error Rate | P95 Latency | P99 Latency |
|-----------|----------|--------|------------|-------------|-------------|
"""

for test_type, summary in sorted(summaries):
    metrics = summary.get('metrics', {})
    http_reqs = metrics.get('http_reqs', {}).get('value', 0)
    http_req_failed = metrics.get('http_req_failed', {}).get('value', 0)
    http_req_duration = metrics.get('http_req_duration', {})
    p95 = http_req_duration.get('values', {}).get('p(95)', 'N/A')
    p99 = http_req_duration.get('values', {}).get('p(99)', 'N/A')
    
    error_rate = (http_req_failed / http_reqs * 100) if http_reqs > 0 else 0
    
    report += f"| {test_type} | {http_reqs} | {http_req_failed:.0f} | {error_rate:.2f}% | {p95}ms | {p99}ms |\n"

report += """
## Thresholds

| Metric | Threshold | Result |
|--------|-----------|--------|
| HTTP P95 Latency | < 500ms | {p95_status} |
| HTTP P99 Latency | < 1000ms | {p99_status} |
| Error Rate | < 5% | {error_status} |

## Details

See individual test result files in `{results_dir}/` directory.
"""

# Write report
with open(report_file, 'w') as f:
    f.write(report)

print(f"Report generated: {report_file}")
PYTHON_EOF
    
    log_success "Report generated"
}

main() {
    log_info "MaaS Load Testing Runner"
    log_info "========================"
    echo ""
    
    check_prerequisites
    echo ""
    
    case "$TEST_TYPE" in
        smoke)
            run_smoke_test
            ;;
        load)
            run_load_test
            ;;
        stress)
            run_stress_test
            ;;
        spike)
            run_spike_test
            ;;
        soak)
            run_soak_test
            ;;
        all)
            run_all_tests
            ;;
        *)
            log_error "Unknown test type: $TEST_TYPE"
            echo "Usage: $0 [smoke|load|stress|spike|soak|all]"
            exit 1
            ;;
    esac
    
    echo ""
    generate_report
    
    log_success "Load testing completed!"
}

main "$@"