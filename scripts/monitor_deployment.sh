#!/bin/bash
# Deployment monitoring script
# Monitors deployment health and metrics

set -e

NAMESPACE=${1:-"x0tta6bl4-staging"}
DURATION=${2:-"300"}  # 5 minutes default

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     Deployment Monitoring Script                            ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check prerequisites
command -v kubectl >/dev/null 2>&1 || { echo "❌ kubectl not found"; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "⚠️  jq not found, JSON parsing will be limited"; }

echo "📊 Monitoring deployment in namespace: $NAMESPACE"
echo "   Duration: ${DURATION}s"
echo ""

# Port forward
echo "🔌 Setting up port forwarding..."
SERVICE_NAME="${NAMESPACE}" # Assuming service name is same as namespace for now
PF_ATTEMPTS=0
MAX_PF_ATTEMPTS=5
PF_SUCCESS=0

while [ $PF_ATTEMPTS -lt $MAX_PF_ATTEMPTS ]; do
    kubectl port-forward -n "$NAMESPACE" svc/"$SERVICE_NAME" 8000:8000 >/dev/null 2>&1 &
    PF_PID=$!
    sleep 5 # Give port-forward some time to establish

    if curl -s http://localhost:8000/health >/dev/null; then
        echo "✅ Port forwarding established to http://localhost:8000"
        PF_SUCCESS=1
        break
    else
        echo "❌ Port forwarding failed on attempt $((PF_ATTEMPTS + 1)). Retrying..."
        kill "$PF_PID" 2>/dev/null || true # Kill previous attempt
        PF_ATTEMPTS=$((PF_ATTEMPTS + 1))
        sleep 5
    fi
done

if [ "$PF_SUCCESS" -eq 0 ]; then
    echo "❌ Failed to establish port forwarding after $MAX_PF_ATTEMPTS attempts. Exiting."
    exit 1
fi

# Cleanup function
cleanup() {
    kill $PF_PID 2>/dev/null || true
    exit 0
}
trap cleanup EXIT INT TERM

# Monitor loop
START_TIME=$(date +%s)
END_TIME=$((START_TIME + DURATION))

while [ $(date +%s) -lt $END_TIME ]; do
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "⏰ $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""
    
    # Pod status
    echo "📦 Pod Status:"
    kubectl get pods -n $NAMESPACE -o wide | grep x0tta6bl4 || echo "No pods found"
    echo ""
    
    # Health check
    echo "🏥 Health Check:"
    if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
        if command -v jq >/dev/null 2>&1; then
            curl -s http://localhost:8000/health | jq '.'
        else
            curl -s http://localhost:8000/health
        fi
    else
        echo "❌ Health check failed"
    fi
    echo ""
    
    # Dependencies
    echo "📋 Dependencies:"
    if curl -sf http://localhost:8000/health/dependencies >/dev/null 2>&1; then
        if command -v jq >/dev/null 2>&1; then
            curl -s http://localhost:8000/health/dependencies | jq '.'
        else
            curl -s http://localhost:8000/health/dependencies
        fi
    else
        echo "❌ Dependencies check failed"
    fi
    echo ""
    
    # Metrics summary
    echo "📊 Metrics Summary:"
    if curl -sf http://localhost:8000/metrics >/dev/null 2>&1; then
        curl -s http://localhost:8000/metrics | grep -E "^x0tta6bl4_" | head -10 || echo "No metrics found"
    else
        echo "❌ Metrics endpoint failed"
    fi
    echo ""
    
    # Resource usage
    echo "💻 Resource Usage:"
    kubectl top pods -n $NAMESPACE 2>/dev/null || echo "Metrics server not available"
    echo ""
    
    sleep 30
done

echo "✅ Monitoring complete"

