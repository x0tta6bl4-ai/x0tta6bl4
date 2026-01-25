#!/bin/bash
# scripts/sprint2/setup_privileged_nodes_self_managed.sh
set -euo pipefail

NODES="${NODES:-node-1 node-2 node-3}"

log() { echo "[$(date -Iseconds)] $*" >&2; }

log "Configuring privileged nodes for self-managed cluster"

for node in $NODES; do
  log "Configuring node: $node"
  kubectl label node "$node" \
    workload=batman-adv \
    security-tier=privileged \
    batman-adv-capable=true \
    apparmor-enabled=true \
    --overwrite || true
  kubectl taint node "$node" privileged-networking=true:NoSchedule --overwrite || true
  log "Node $node configured"
done

log "Verifying configuration..."
kubectl get nodes -l workload=batman-adv -o wide
log "Node configuration complete!"
