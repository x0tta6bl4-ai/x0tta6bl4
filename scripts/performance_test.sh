#!/bin/bash
# Performance testing script for x0tta6bl4
# Tests latency, throughput, and resource usage

set -e

BASE_URL="${1:-http://localhost:8080}"
DURATION="${2:-60}"
CONCURRENT="${3:-10}"

echo "🚀 Performance Testing for x0tta6bl4"
echo "Base URL: $BASE_URL"
echo "Duration: ${DURATION}s"
echo "Concurrent: $CONCURRENT"
echo ""

# Check if server is running
if ! curl -s "$BASE_URL/health" > /dev/null; then
    echo "❌ Server not responding at $BASE_URL"
    exit 1
fi

echo "📊 Running performance tests..."

# 1. Health endpoint latency
echo "1️⃣  Testing health endpoint latency..."
HEALTH_LATENCY=$(for i in {1..100}; do
    curl -s -o /dev/null -w "%{time_total}\n" "$BASE_URL/health"
done | awk '{sum+=$1; count++} END {print sum/count}')

echo "   Average latency: ${HEALTH_LATENCY}s"

# 2. Throughput test
echo "2️⃣  Testing throughput..."
if command -v ab &> /dev/null; then
    ab -n 1000 -c "$CONCURRENT" "$BASE_URL/health" 2>&1 | grep -E "Requests per second|Time per request" || true
else
    echo "   Install Apache Bench (ab) for throughput testing"
fi

# 3. Memory usage (if running in container)
echo "3️⃣  Checking resource usage..."
if command -v docker &> /dev/null; then
    CONTAINER_ID=$(docker ps --filter "ancestor=x0tta6bl4" -q | head -1)
    if [ -n "$CONTAINER_ID" ]; then
        docker stats --no-stream "$CONTAINER_ID" 2>/dev/null || true
    fi
fi

# 4. Load test with curl
echo "4️⃣  Running load test..."
START_TIME=$(date +%s)
SUCCESS=0
FAILED=0

for i in $(seq 1 $DURATION); do
    for j in $(seq 1 $CONCURRENT); do
        if curl -s "$BASE_URL/health" > /dev/null; then
            ((SUCCESS++))
        else
            ((FAILED++))
        fi
    done
    sleep 1
    echo -n "."
done

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

echo ""
echo "📊 Results:"
echo "   Duration: ${ELAPSED}s"
echo "   Successful requests: $SUCCESS"
echo "   Failed requests: $FAILED"
echo "   Requests/sec: $((SUCCESS / ELAPSED))"

# 5. Check response times
echo "5️⃣  Testing response times..."
RESPONSE_TIMES=$(for i in {1..50}; do
    curl -s -o /dev/null -w "%{time_total}\n" "$BASE_URL/health"
done | sort -n)

P50=$(echo "$RESPONSE_TIMES" | awk 'NR==25')
P95=$(echo "$RESPONSE_TIMES" | awk 'NR==47')
P99=$(echo "$RESPONSE_TIMES" | awk 'NR==49')

echo "   P50: ${P50}s"
echo "   P95: ${P95}s"
echo "   P99: ${P99}s"

echo ""
echo "✅ Performance testing complete"

