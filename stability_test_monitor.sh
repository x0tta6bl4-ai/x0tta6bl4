#!/bin/bash
# Stability Test Monitor
# Monitors system for 24+ hours

DURATION=${1:-86400}  # Default 24 hours in seconds
INTERVAL=${2:-300}    # Default 5 minutes
LOG_FILE="stability_test_$(date +%Y%m%d_%H%M%S).log"
KUBECONFIG=${KUBECONFIG:-/tmp/kind-kubeconfig.yaml}

export KUBECONFIG

echo "Starting stability test monitoring at $(date)" | tee -a $LOG_FILE
echo "Duration: $DURATION seconds ($(($DURATION / 3600)) hours)" | tee -a $LOG_FILE
echo "Interval: $INTERVAL seconds ($(($INTERVAL / 60)) minutes)" | tee -a $LOG_FILE
echo "" | tee -a $LOG_FILE

ITERATIONS=$(($DURATION / $INTERVAL))

for ((i=1; i<=$ITERATIONS; i++)); do
    TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")
    ELAPSED=$(($i * $INTERVAL))
    HOURS=$(($ELAPSED / 3600))
    MINUTES=$((($ELAPSED % 3600) / 60))
    
    echo "=== Iteration $i/$ITERATIONS - Elapsed: ${HOURS}h ${MINUTES}m - $TIMESTAMP ===" | tee -a $LOG_FILE
    
    # Check pods status
    echo "Pods status:" | tee -a $LOG_FILE
    kubectl get pods -n x0tta6bl4-staging 2>&1 | tee -a $LOG_FILE
    
    # Check health
    echo "Health check:" | tee -a $LOG_FILE
    curl -s http://localhost:8080/health 2>&1 | python3 -m json.tool 2>/dev/null | head -10 | tee -a $LOG_FILE
    
    # Check GNN metrics
    echo "GNN recall:" | tee -a $LOG_FILE
    curl -s http://localhost:8080/metrics 2>&1 | grep gnn_recall_score | tee -a $LOG_FILE
    
    # Check mesh metrics
    echo "Mesh metrics:" | tee -a $LOG_FILE
    curl -s http://localhost:8080/metrics 2>&1 | grep -E "mesh_mape_k_|mesh_mttd" | head -5 | tee -a $LOG_FILE
    
    # Check resource usage (if metrics-server available)
    echo "Resource usage:" | tee -a $LOG_FILE
    kubectl top pods -n x0tta6bl4-staging 2>&1 | tee -a $LOG_FILE
    
    echo "" | tee -a $LOG_FILE
    
    sleep $INTERVAL
done

echo "Stability test monitoring completed at $(date)" | tee -a $LOG_FILE
