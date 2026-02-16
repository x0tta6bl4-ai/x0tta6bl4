#!/bin/bash
# Quick Health Check Script
# Быстрая проверка состояния deployment

KUBECONFIG=${KUBECONFIG:-/tmp/kind-kubeconfig.yaml}
export KUBECONFIG

NAMESPACE="x0tta6bl4-staging"
SERVICE_URL="http://localhost:8080"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║          Quick Health Check - x0tta6bl4 Staging             ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check pods
echo "📊 Pods Status:"
kubectl get pods -n $NAMESPACE --no-headers | while read line; do
    POD_NAME=$(echo $line | awk '{print $1}')
    STATUS=$(echo $line | awk '{print $3}')
    READY=$(echo $line | awk '{print $2}')
    RESTARTS=$(echo $line | awk '{print $4}')
    
    if [ "$STATUS" = "Running" ] && [[ "$READY" == *"/1" ]]; then
        echo "  ✅ $POD_NAME: $STATUS, $READY, Restarts: $RESTARTS"
    else
        echo "  ⚠️  $POD_NAME: $STATUS, $READY, Restarts: $RESTARTS"
    fi
done

echo ""

# Check health endpoint
echo "🏥 Health Endpoint:"
HEALTH_RESPONSE=$(curl -s -w "\n%{http_code}" $SERVICE_URL/health 2>/dev/null)
HTTP_CODE=$(echo "$HEALTH_RESPONSE" | tail -1)
BODY=$(echo "$HEALTH_RESPONSE" | head -n -1)

if [ "$HTTP_CODE" = "200" ]; then
    echo "  ✅ HTTP $HTTP_CODE"
    echo "$BODY" | jq . 2>/dev/null || echo "$BODY"
else
    echo "  ⚠️  HTTP $HTTP_CODE"
    echo "$BODY"
fi

echo ""

# Check ready endpoint
echo "✅ Ready Endpoint:"
READY_RESPONSE=$(curl -s -w "\n%{http_code}" $SERVICE_URL/ready 2>/dev/null)
HTTP_CODE=$(echo "$READY_RESPONSE" | tail -1)
BODY=$(echo "$READY_RESPONSE" | head -n -1)

if [ "$HTTP_CODE" = "200" ]; then
    echo "  ✅ HTTP $HTTP_CODE"
    echo "$BODY" | jq . 2>/dev/null || echo "$BODY"
else
    echo "  ⚠️  HTTP $HTTP_CODE"
    echo "$BODY"
fi

echo ""

# Check metrics
echo "📈 Metrics Endpoint:"
METRICS_RESPONSE=$(curl -s -w "\n%{http_code}" $SERVICE_URL/metrics 2>/dev/null)
HTTP_CODE=$(echo "$METRICS_RESPONSE" | tail -1)

if [ "$HTTP_CODE" = "200" ]; then
    echo "  ✅ HTTP $HTTP_CODE"
    METRIC_COUNT=$(echo "$METRICS_RESPONSE" | head -n -1 | grep -c "^[^#]" || echo "0")
    echo "  📊 Total metrics: $METRIC_COUNT"
    
    # Key metrics
    echo ""
    echo "  Key Metrics:"
    echo "$METRICS_RESPONSE" | head -n -1 | grep -E "(gnn_recall|mesh_mape_k_|mesh_mttd|mesh_peers)" | head -5 | while read metric; do
        echo "    • $metric"
    done
else
    echo "  ⚠️  HTTP $HTTP_CODE"
fi

echo ""

# Check mesh status
echo "🌐 Mesh Status:"
MESH_RESPONSE=$(curl -s -w "\n%{http_code}" $SERVICE_URL/mesh/status 2>/dev/null)
HTTP_CODE=$(echo "$MESH_RESPONSE" | tail -1)
BODY=$(echo "$MESH_RESPONSE" | head -n -1)

if [ "$HTTP_CODE" = "200" ]; then
    echo "  ✅ HTTP $HTTP_CODE"
    echo "$BODY" | jq . 2>/dev/null || echo "$BODY"
else
    echo "  ⚠️  HTTP $HTTP_CODE"
    echo "$BODY"
fi

echo ""

# Summary
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║          Summary                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"

POD_COUNT=$(kubectl get pods -n $NAMESPACE --no-headers | wc -l)
READY_COUNT=$(kubectl get pods -n $NAMESPACE --no-headers | grep -c "Running.*1/1" || echo "0")

if [ "$READY_COUNT" -eq "$POD_COUNT" ] && [ "$POD_COUNT" -gt 0 ]; then
    echo "✅ All pods healthy: $READY_COUNT/$POD_COUNT"
else
    echo "⚠️  Pods status: $READY_COUNT/$POD_COUNT ready"
fi

if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ Health endpoint: OK"
else
    echo "⚠️  Health endpoint: Issues detected"
fi

echo ""
echo "Timestamp: $(date)"
echo ""

