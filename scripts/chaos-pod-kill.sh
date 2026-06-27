#!/bin/bash
# Chaos Engineering Test Script
# Tests MTTR (Mean Time To Recovery) by killing pods

set -e

NAMESPACE="mesh-system"
CONTEXT="kind-x0tta6bl4-local"
LABEL="app=mesh-node"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║       CHAOS ENGINEERING: Pod Kill Test                       ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║  Target: MTTR ≤ 5 seconds                                    ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Get initial pod count
INITIAL_PODS=$(kubectl get pods -n $NAMESPACE -l $LABEL --context $CONTEXT -o name | wc -l)
echo "📊 Initial pods: $INITIAL_PODS"

# Calculate 25% of pods to kill
KILL_COUNT=$((INITIAL_PODS / 4))
if [ $KILL_COUNT -lt 1 ]; then
    KILL_COUNT=1
fi
echo "🎯 Killing $KILL_COUNT pods (25%)"
echo ""

# Get pod names to kill
PODS_TO_KILL=$(kubectl get pods -n $NAMESPACE -l $LABEL --context $CONTEXT -o name | head -n $KILL_COUNT)

# Record start time
START_TIME=$(date +%s.%N)
echo "⏱️  START: $(date '+%H:%M:%S.%3N')"

# Kill pods
echo "💀 Killing pods..."
for pod in $PODS_TO_KILL; do
    kubectl delete $pod -n $NAMESPACE --context $CONTEXT --grace-period=0 --force 2>/dev/null &
done
wait

echo "🔄 Waiting for recovery..."

# Wait for recovery (all pods running again)
while true; do
    CURRENT_READY=$(kubectl get pods -n $NAMESPACE -l $LABEL --context $CONTEXT --no-headers 2>/dev/null | grep -c "Running" || echo "0")
    
    if [ "$CURRENT_READY" -ge "$INITIAL_PODS" ]; then
        END_TIME=$(date +%s.%N)
        break
    fi
    
    # Timeout after 30 seconds
    ELAPSED=$(echo "$(date +%s.%N) - $START_TIME" | bc)
    if (( $(echo "$ELAPSED > 30" | bc -l) )); then
        echo "❌ TIMEOUT: Recovery took > 30 seconds"
        exit 1
    fi
    
    sleep 0.5
done

echo "⏱️  END: $(date '+%H:%M:%S.%3N')"

# Calculate MTTR
MTTR=$(echo "$END_TIME - $START_TIME" | bc)
echo ""
echo "════════════════════════════════════════════════════════════════"
echo "📊 RESULTS:"
echo "   Pods Killed: $KILL_COUNT"
echo "   MTTR: ${MTTR}s"

if (( $(echo "$MTTR <= 5" | bc -l) )); then
    echo "   ✅ PASS: MTTR ≤ 5s target met!"
    echo "════════════════════════════════════════════════════════════════"
    exit 0
else
    echo "   ❌ FAIL: MTTR > 5s"
    echo "════════════════════════════════════════════════════════════════"
    exit 1
fi
