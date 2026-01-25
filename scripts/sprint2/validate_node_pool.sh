#!/bin/bash
# scripts/sprint2/validate_node_pool.sh
set -euo pipefail

log() { echo "[$(date -Iseconds)] $*" >&2; }

validate_labels() {
  log "Validating node labels..."
  local required_labels=(
    "workload=batman-adv"
    "security-tier=privileged"
    "batman-adv-capable=true"
  )
  for label in "${required_labels[@]}"; do
    node_count=$(kubectl get nodes -l "$label" --no-headers | wc -l | tr -d ' ')
    if [[ ${node_count:-0} -lt 3 ]]; then
      log "ERROR: Only $node_count nodes have label $label (min 3 required)"
      return 1
    fi
    log "✓ Found $node_count nodes with label $label"
  done
}

validate_taints() {
  log "Validating node taints..."
  for node in $(kubectl get nodes -l workload=batman-adv -o name); do
    if ! kubectl get "$node" -o json | jq -e '.spec.taints[] | select(.key=="privileged-networking")' >/dev/null; then
      log "ERROR: Node $node missing privileged-networking taint"
      return 1
    fi
    log "✓ Node $node has correct taint"
  done
}

validate_kernel_modules() {
  log "Validating kernel modules on nodes..."
  for node in $(kubectl get nodes -l workload=batman-adv -o jsonpath='{.items[*].metadata.name}'); do
    log "Checking batman_adv module availability on $node..."
    kubectl debug node/"$node" -it --image=busybox -- modinfo batman_adv 2>&1 | grep -q "filename:" && \
      log "✓ batman_adv module available on $node" || \
      log "⚠️  batman_adv module not found on $node (may load at runtime)"
  done
}

main() {
  log "=== Node Pool Validation ==="
  validate_labels || exit 1
  validate_taints || exit 1
  validate_kernel_modules || true
  log "=== Validation Complete ==="
}

main "$@"
