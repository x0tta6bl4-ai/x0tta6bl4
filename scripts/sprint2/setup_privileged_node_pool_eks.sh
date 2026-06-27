#!/bin/bash
# scripts/sprint2/setup_privileged_node_pool_eks.sh
set -euo pipefail

CLUSTER_NAME="${CLUSTER_NAME:-mesh-production}"
NODE_GROUP_NAME="batman-adv-privileged"
NODE_TYPE="${NODE_TYPE:-t3.medium}"
MIN_NODES=${MIN_NODES:-3}
MAX_NODES=${MAX_NODES:-5}

log() { echo "[$(date -Iseconds)] $*" >&2; }

log "Creating privileged node pool for EKS cluster: $CLUSTER_NAME"

eksctl create nodegroup \
  --cluster "$CLUSTER_NAME" \
  --name "$NODE_GROUP_NAME" \
  --node-type "$NODE_TYPE" \
  --nodes "$MIN_NODES" \
  --nodes-min "$MIN_NODES" \
  --nodes-max "$MAX_NODES" \
  --node-labels "workload=batman-adv,security-tier=privileged,mesh-capable=true" \
  --node-taints "privileged-networking=true:NoSchedule" \
  --node-private-networking \
  --managed

log "Waiting for nodes to be ready..."
kubectl wait --for=condition=Ready nodes -l workload=batman-adv --timeout=300s || true

log "Applying additional labels..."
for node in $(kubectl get nodes -l workload=batman-adv -o name); do
  kubectl label "$node" batman-adv-capable=true --overwrite || true
  kubectl label "$node" apparmor-enabled=true --overwrite || true
done

log "Node pool created successfully!"
kubectl get nodes -l workload=batman-adv -o wide
