#!/bin/bash
# Load testing script for x0tta6bl4
# Usage: ./scripts/load_test.sh [endpoint] [duration] [concurrent]

set -e

ENDPOINT=${1:-"http://localhost:8000"}
DURATION=${2:-"60s"}
CONCURRENT=${3:-"10"}

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     Load Testing Script                                      ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check if k6 is available
if ! command -v k6 &> /dev/null; then
    echo "⚠️  k6 not found. Installing..."
    # Try to use local k6 if available
    if [ -f "./k6" ]; then
        K6_CMD="./k6"
    else
        echo "❌ k6 not found. Please install k6: https://k6.io/docs/getting-started/installation/"
        exit 1
    fi
else
    K6_CMD="k6"
fi

echo "📊 Load Test Configuration:"
echo "   Endpoint: $ENDPOINT"
echo "   Duration: $DURATION"
echo "   Concurrent: $CONCURRENT"
echo ""

# Create k6 script
cat > /tmp/k6_load_test.js <<EOF
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

const errorRate = new Rate('errors');

export const options = {
    stages: [
        { duration: '10s', target: ${CONCURRENT} },
        { duration: '${DURATION}', target: ${CONCURRENT} },
        { duration: '10s', target: 0 },
    ],
    thresholds: {
        http_req_duration: ['p(95)<500', 'p(99)<1000'],
        http_req_failed: ['rate<0.01'],
        errors: ['rate<0.01'],
    },
};

export default function () {
    // Health check
    const healthRes = http.get('${ENDPOINT}/health');
    check(healthRes, {
        'health status is 200': (r) => r.status === 200,
        'health response time < 500ms': (r) => r.timings.duration < 500,
    }) || errorRate.add(1);

    // Dependencies check
    const depsRes = http.get('${ENDPOINT}/health/dependencies');
    check(depsRes, {
        'dependencies status is 200': (r) => r.status === 200,
    }) || errorRate.add(1);

    sleep(1);
}
EOF

echo "🚀 Running load test..."
$K6_CMD run /tmp/k6_load_test.js

echo ""
echo "✅ Load test complete!"

