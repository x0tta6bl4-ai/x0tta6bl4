#!/bin/bash
# Full Cluster Test for x0tta6bl4
set -e

NAMESPACE="mesh-system"
CONTEXT="kind-x0tta6bl4-local"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║       x0tta6bl4 FULL CLUSTER TEST                            ║"
echo "║       Server: Kind ($CONTEXT)                                ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

PASS=0
FAIL=0

test_result() {
    if [ "$1" = "pass" ]; then
        echo "   ✅ $2"
        ((PASS++))
    else
        echo "   ❌ $2"
        ((FAIL++))
    fi
}

# Test 1: Cluster Health
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧪 TEST 1: Cluster Health"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

NODES=$(kubectl get nodes --context $CONTEXT --no-headers 2>/dev/null | grep -c "Ready" || echo "0")
if [ "$NODES" -ge "1" ]; then
    test_result "pass" "Nodes ready: $NODES"
else
    test_result "fail" "No ready nodes"
fi

PODS=$(kubectl get pods -n $NAMESPACE --context $CONTEXT --no-headers 2>/dev/null | grep -c "Running" || echo "0")
if [ "$PODS" -ge "3" ]; then
    test_result "pass" "Mesh pods running: $PODS"
else
    test_result "fail" "Not enough mesh pods: $PODS"
fi

# Test 2: Pod Recovery (MTTR)
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧪 TEST 2: Self-Healing (MTTR)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

POD=$(kubectl get pods -n $NAMESPACE --context $CONTEXT -o name | head -1)
INITIAL=$(kubectl get pods -n $NAMESPACE --context $CONTEXT --no-headers | grep -c "Running")

echo "   Killing pod: $POD"
START=$(date +%s.%N)
kubectl delete $POD -n $NAMESPACE --context $CONTEXT --grace-period=0 --force 2>/dev/null &
wait

# Wait for recovery
while true; do
    CURRENT=$(kubectl get pods -n $NAMESPACE --context $CONTEXT --no-headers 2>/dev/null | grep -c "Running" || echo "0")
    if [ "$CURRENT" -ge "$INITIAL" ]; then
        END=$(date +%s.%N)
        break
    fi
    sleep 0.5
done

MTTR=$(echo "$END - $START" | bc)
echo "   MTTR: ${MTTR}s"

if (( $(echo "$MTTR <= 5" | bc -l) )); then
    test_result "pass" "MTTR ≤ 5s (${MTTR}s)"
else
    test_result "fail" "MTTR > 5s (${MTTR}s)"
fi

# Test 3: Monitoring Stack
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧪 TEST 3: Monitoring Stack"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

PROM=$(kubectl get pods -n monitoring --context $CONTEXT --no-headers 2>/dev/null | grep -c "prometheus" || echo "0")
if [ "$PROM" -ge "1" ]; then
    test_result "pass" "Prometheus running"
else
    test_result "fail" "Prometheus not found"
fi

GRAFANA=$(kubectl get pods -n monitoring --context $CONTEXT --no-headers 2>/dev/null | grep -c "grafana" || echo "0")
if [ "$GRAFANA" -ge "1" ]; then
    test_result "pass" "Grafana running"
else
    test_result "fail" "Grafana not found"
fi

# Test 4: Autoscaling
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧪 TEST 4: Autoscaling (Scale 4→6→4)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo "   Scaling to 6 replicas..."
kubectl scale deployment mesh-node -n $NAMESPACE --replicas=6 --context $CONTEXT 2>/dev/null

sleep 15
SCALED=$(kubectl get pods -n $NAMESPACE --context $CONTEXT --no-headers | grep -c "Running" || echo "0")
echo "   Pods after scale-up: $SCALED"

if [ "$SCALED" -ge "5" ]; then
    test_result "pass" "Scale-up successful ($SCALED pods)"
else
    test_result "fail" "Scale-up failed ($SCALED pods)"
fi

echo "   Scaling back to 4 replicas..."
kubectl scale deployment mesh-node -n $NAMESPACE --replicas=4 --context $CONTEXT 2>/dev/null

sleep 10
FINAL=$(kubectl get pods -n $NAMESPACE --context $CONTEXT --no-headers | grep -c "Running" || echo "0")
echo "   Pods after scale-down: $FINAL"

if [ "$FINAL" -le "5" ]; then
    test_result "pass" "Scale-down successful ($FINAL pods)"
else
    test_result "fail" "Scale-down incomplete ($FINAL pods)"
fi

# Test 5: Stress Test (rapid kills)
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧪 TEST 5: Stress Test (3 rapid pod kills)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

TOTAL_MTTR=0
for i in 1 2 3; do
    POD=$(kubectl get pods -n $NAMESPACE --context $CONTEXT -o name | shuf -n 1)
    START=$(date +%s.%N)
    kubectl delete $POD -n $NAMESPACE --context $CONTEXT --grace-period=0 --force 2>/dev/null &
    wait
    
    while true; do
        READY=$(kubectl get pods -n $NAMESPACE --context $CONTEXT --no-headers 2>/dev/null | grep -c "Running" || echo "0")
        if [ "$READY" -ge "4" ]; then
            END=$(date +%s.%N)
            break
        fi
        sleep 0.5
    done
    
    KILL_MTTR=$(echo "$END - $START" | bc)
    TOTAL_MTTR=$(echo "$TOTAL_MTTR + $KILL_MTTR" | bc)
    echo "   Kill #$i: ${KILL_MTTR}s"
    sleep 2
done

AVG_MTTR=$(echo "scale=2; $TOTAL_MTTR / 3" | bc)
echo "   Average MTTR: ${AVG_MTTR}s"

if (( $(echo "$AVG_MTTR <= 5" | bc -l) )); then
    test_result "pass" "Stress test MTTR ≤ 5s (${AVG_MTTR}s)"
else
    test_result "fail" "Stress test MTTR > 5s (${AVG_MTTR}s)"
fi

# Summary
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                    TEST SUMMARY                              ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║                                                              ║"
echo "║  Passed: $PASS                                                ║"
echo "║  Failed: $FAIL                                                ║"
echo "║                                                              ║"

TOTAL=$((PASS + FAIL))
SCORE=$((PASS * 100 / TOTAL))

if [ $FAIL -eq 0 ]; then
    echo "║  🏆 ALL TESTS PASSED! Score: ${SCORE}%                        ║"
    echo "║                                                              ║"
    echo "║  Server: kind-x0tta6bl4-local                                ║"
    echo "║  Status: PRODUCTION READY ✅                                 ║"
else
    echo "║  ⚠️  Some tests failed. Score: ${SCORE}%                      ║"
fi

echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"

exit $FAIL
