#!/bin/bash
# Monitoring Dashboard Script
# Real-time monitoring of x0tta6bl4 staging deployment

KUBECONFIG=${KUBECONFIG:-/tmp/kind-kubeconfig.yaml}
export KUBECONFIG

NAMESPACE="x0tta6bl4-staging"
SERVICE_URL="http://localhost:8080"
REFRESH_INTERVAL=${1:-5}

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

clear_screen() {
    clear
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║     x0tta6bl4 Staging - Real-time Monitoring Dashboard      ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo "Refresh interval: ${REFRESH_INTERVAL}s | Press Ctrl+C to exit"
    echo ""
}

get_pod_status() {
    kubectl get pods -n $NAMESPACE --no-headers 2>/dev/null | while read line; do
        POD_NAME=$(echo $line | awk '{print $1}')
        STATUS=$(echo $line | awk '{print $3}')
        READY=$(echo $line | awk '{print $2}')
        RESTARTS=$(echo $line | awk '{print $4}')
        
        if [ "$STATUS" = "Running" ] && [[ "$READY" == *"/1" ]]; then
            echo -e "${GREEN}✅${NC} $POD_NAME: $STATUS, $READY, Restarts: $RESTARTS"
        else
            echo -e "${YELLOW}⚠️${NC}  $POD_NAME: $STATUS, $READY, Restarts: $RESTARTS"
        fi
    done
}

get_health_status() {
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" $SERVICE_URL/health 2>/dev/null)
    if [ "$HTTP_CODE" = "200" ]; then
        echo -e "${GREEN}✅ Health: OK${NC} (HTTP $HTTP_CODE)"
    else
        echo -e "${RED}❌ Health: FAILED${NC} (HTTP $HTTP_CODE)"
    fi
}

get_metrics_summary() {
    METRICS=$(curl -s $SERVICE_URL/metrics 2>/dev/null)
    
    if [ -n "$METRICS" ]; then
        GNN_RECALL=$(echo "$METRICS" | grep "gnn_recall" | grep -v "#" | awk '{print $2}' | head -1)
        MESH_PEERS=$(echo "$METRICS" | grep "mesh_peers" | grep -v "#" | awk '{print $2}' | head -1)
        MAPE_K_ACTIVE=$(echo "$METRICS" | grep "mesh_mape_k_active" | grep -v "#" | awk '{print $2}' | head -1)
        
        echo "📊 Metrics:"
        if [ -n "$GNN_RECALL" ]; then
            echo "  • GNN Recall: $GNN_RECALL"
        fi
        if [ -n "$MESH_PEERS" ]; then
            echo "  • Mesh Peers: $MESH_PEERS"
        fi
        if [ -n "$MAPE_K_ACTIVE" ]; then
            if [ "$MAPE_K_ACTIVE" = "1" ]; then
                echo -e "  • MAPE-K: ${GREEN}Active${NC}"
            else
                echo -e "  • MAPE-K: ${YELLOW}Inactive${NC}"
            fi
        fi
    fi
}

get_mesh_status() {
    MESH_STATUS=$(curl -s $SERVICE_URL/mesh/status 2>/dev/null)
    if [ -n "$MESH_STATUS" ]; then
        echo "🌐 Mesh Status:"
        echo "$MESH_STATUS" | jq -r '.peers // .status // "Unknown"' 2>/dev/null || echo "  Available"
    fi
}

# Main loop
while true; do
    clear_screen
    
    echo "📦 Pods:"
    get_pod_status
    echo ""
    
    echo "🏥 Health:"
    get_health_status
    echo ""
    
    get_metrics_summary
    echo ""
    
    get_mesh_status
    echo ""
    
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║ Last update: $(date '+%Y-%m-%d %H:%M:%S')                              ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    
    sleep $REFRESH_INTERVAL
done

