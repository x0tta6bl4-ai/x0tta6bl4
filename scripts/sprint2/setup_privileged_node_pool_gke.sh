#!/bin/bash
# scripts/sprint2/setup_privileged_node_pool_gke.sh
set -euo pipefail

CLUSTER_NAME="${CLUSTER_NAME:-mesh-production}"
NODE_POOL_NAME="batman-adv-privileged"
MACHINE_TYPE="${MACHINE_TYPE:-n1-standard-2}"
MIN_NODES=${MIN_NODES:-3}
MAX_NODES=${MAX_NODES:-5}
ZONE="${ZONE:-us-central1-a}"

log() { echo "[$(date -Iseconds)] $*" >&2; }

log "Creating privileged node pool for GKE cluster: $CLUSTER_NAME"

gcloud container node-pools create "$NODE_POOL_NAME" \
  --cluster="$CLUSTER_NAME" \
  --zone="$ZONE" \
  --machine-type="$MACHINE_TYPE" \
  --num-nodes="$MIN_NODES" \
  --enable-autoscaling \
  --min-nodes="$MIN_NODES" \
  --max-nodes="$MAX_NODES" \
  --node-labels=workload=batman-adv,security-tier=privileged,batman-adv-capable=true \
  --node-taints=privileged-networking=true:NoSchedule \
  --scopes=gke-default \
  --enable-autorepair \
  --enable-autoupgrade

log "Waiting for node pool creation..."
# Note: Simplified wait; adapt to your env if needed
sleep 20

log "Node pool created successfully!"
kubectl get nodes -l workload=batman-adv -o wide
