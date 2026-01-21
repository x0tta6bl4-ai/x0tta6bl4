#!/bin/bash
# Failure Injection Test Script
# Tests self-healing mechanisms (MAPE-K, GraphSAGE)

KUBECONFIG=${KUBECONFIG:-/tmp/kind-kubeconfig.yaml}
export KUBECONFIG

NAMESPACE="x0tta6bl4-staging"
LOG_FILE="failure_injection_test_$(date +%Y%m%d_%H%M%S).log"

echo "Starting failure injection tests at $(date)" | tee -a $LOG_FILE
echo "Namespace: $NAMESPACE" | tee -a $LOG_FILE
echo "" | tee -a $LOG_FILE

# Test 1: Pod Failure
echo "=== TEST 1: Pod Failure (Kill Pod) ===" | tee -a $LOG_FILE
echo "Getting pod list..." | tee -a $LOG_FILE
PODS=$(kubectl get pods -n $NAMESPACE -o jsonpath='{.items[*].metadata.name}')
POD_TO_KILL=$(echo "$PODS" | cut -d' ' -f1)
echo "Selected pod to kill: $POD_TO_KILL" | tee -a $LOG_FILE

# Get initial state
echo "Initial state:" | tee -a $LOG_FILE
kubectl get pods -n $NAMESPACE | tee -a $LOG_FILE
INITIAL_TIME=$(date +%s)

# Kill pod
echo "Killing pod: $POD_TO_KILL" | tee -a $LOG_FILE
kubectl delete pod "$POD_TO_KILL" -n $NAMESPACE 2>&1 | tee -a $LOG_FILE

# Monitor recovery
echo "Monitoring recovery..." | tee -a $LOG_FILE
RECOVERED=false
for i in {1..60}; do
    sleep 5
    READY_COUNT=$(kubectl get pods -n $NAMESPACE -o jsonpath='{.items[*].status.containerStatuses[0].ready}' | grep -o "true" | wc -l)
    TOTAL_COUNT=$(kubectl get pods -n $NAMESPACE -o jsonpath='{.items[*].metadata.name}' | wc -w)
    
    if [ "$READY_COUNT" -eq "$TOTAL_COUNT" ] && [ "$TOTAL_COUNT" -eq "5" ]; then
        RECOVERED=true
        RECOVERY_TIME=$(date +%s)
        MTTR=$((RECOVERY_TIME - INITIAL_TIME))
        echo "✅ Pod recovered! MTTR: ${MTTR}s" | tee -a $LOG_FILE
        break
    fi
    
    echo "  Iteration $i: Ready=$READY_COUNT/$TOTAL_COUNT" | tee -a $LOG_FILE
done

if [ "$RECOVERED" = false ]; then
    echo "⚠️  Pod did not recover within 5 minutes" | tee -a $LOG_FILE
fi

# Check mesh status
echo "Checking mesh status..." | tee -a $LOG_FILE
curl -s http://localhost:8080/mesh/status 2>&1 | python3 -m json.tool 2>/dev/null | head -10 | tee -a $LOG_FILE

# Check MAPE-K metrics
echo "Checking MAPE-K metrics..." | tee -a $LOG_FILE
curl -s http://localhost:8080/metrics 2>&1 | grep -E "mesh_mape_k_|mesh_mttd" | head -10 | tee -a $LOG_FILE

echo "" | tee -a $LOG_FILE
echo "=== TEST 1 COMPLETED ===" | tee -a $LOG_FILE
echo "" | tee -a $LOG_FILE

# Wait before next test
echo "Waiting 2 minutes before next test..." | tee -a $LOG_FILE
sleep 120

# Test 2: High Load
echo "=== TEST 2: High Load Injection ===" | tee -a $LOG_FILE
echo "Starting high load test (1000 requests)..." | tee -a $LOG_FILE
START_TIME=$(date +%s)

for i in {1..1000}; do
    curl -s http://localhost:8080/health > /dev/null &
    if [ $((i % 100)) -eq 0 ]; then
        echo "  Sent $i requests..." | tee -a $LOG_FILE
    fi
done
wait

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
echo "✅ High load test completed in ${DURATION}s" | tee -a $LOG_FILE

# Check system state after load
echo "Checking system state after load..." | tee -a $LOG_FILE
kubectl get pods -n $NAMESPACE | tee -a $LOG_FILE
curl -s http://localhost:8080/health 2>&1 | python3 -m json.tool 2>/dev/null | head -5 | tee -a $LOG_FILE

echo "" | tee -a $LOG_FILE
echo "=== TEST 2 COMPLETED ===" | tee -a $LOG_FILE
echo "" | tee -a $LOG_FILE

# Wait before next test
echo "Waiting 2 minutes before next test..." | tee -a $LOG_FILE
sleep 120

# Test 3: Resource Exhaustion (CPU Stress)
echo "=== TEST 3: Resource Exhaustion (CPU Stress) ===" | tee -a $LOG_FILE
echo "Getting pod list..." | tee -a $LOG_FILE
PODS_FOR_STRESS=$(kubectl get pods -n $NAMESPACE -o jsonpath='{.items[*].metadata.name}')
POD_TO_STRESS=$(echo "$PODS_FOR_STRESS" | cut -d' ' -f1)
echo "Selected pod to stress: $POD_TO_STRESS" | tee -a $LOG_FILE

# Start CPU stress in the background
echo "Stressing CPU on pod $POD_TO_STRESS for 60 seconds..." | tee -a $LOG_FILE
kubectl exec -n $NAMESPACE "$POD_TO_STRESS" -- /bin/sh -c "while true; do :; done" > /dev/null 2>&1 &
STRESS_PID=$!
echo "Stress process started with PID: $STRESS_PID" | tee -a $LOG_FILE

# Monitor health during stress
SUCCESS_COUNT=0
echo "Monitoring health for 60 seconds..." | tee -a $LOG_FILE
for i in {1..12}; do
    sleep 5
    if curl -s --max-time 2 http://localhost:8080/health > /dev/null; then
        echo "  Iteration $i: Health check PASSED" | tee -a $LOG_FILE
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    else
        echo "  Iteration $i: Health check FAILED" | tee -a $LOG_FILE
    fi
done

echo "Stopping CPU stress..." | tee -a $LOG_FILE
kill $STRESS_PID
wait $STRESS_PID 2>/dev/null
echo "Stress process stopped." | tee -a $LOG_FILE

# Verify system returns to normal
echo "Verifying system state after stress..." | tee -a $LOG_FILE
sleep 10
FINAL_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/health)
if [ "$FINAL_HEALTH" -eq 200 ]; then
    echo "✅ System health is normal after stress test." | tee -a $LOG_FILE
else
    echo "⚠️ System health is ABNORMAL after stress test (HTTP code: $FINAL_HEALTH)" | tee -a $LOG_FILE
fi

echo "" | tee -a $LOG_FILE
echo "=== TEST 3 COMPLETED ===" | tee -a $LOG_FILE
echo "" | tee -a $LOG_FILE

echo "Failure injection tests completed at $(date)" | tee -a $LOG_FILE
echo "Results saved to: $LOG_FILE" | tee -a $LOG_FILE