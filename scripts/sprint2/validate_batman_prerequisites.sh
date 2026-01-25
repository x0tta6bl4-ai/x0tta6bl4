#!/bin/bash
# scripts/sprint2/validate_batman_prerequisites.sh
set -euo pipefail

log() { echo "[$(date -Iseconds)] $*" >&2; }

check_node_pool() {
  log "Checking node pool configuration..."
  node_count=$(kubectl get nodes -l batman-adv-capable=true --no-headers | wc -l | tr -d ' ')
  if [[ ${node_count:-0} -lt 3 ]]; then
    log "✗ ERROR: Need at least 3 batman-adv-capable nodes (found: $node_count)"
    return 1
  fi
  log "✓ Found $node_count batman-adv-capable nodes"
}

check_apparmor() {
  log "Checking AppArmor profiles..."
  for node in $(kubectl get nodes -l batman-adv-capable=true -o jsonpath='{.items[*].metadata.name}'); do
    if kubectl debug node/"$node" -it --image=ubuntu:22.04 -- aa-status 2>&1 | grep -q batman-adv-profile; then
      log "✓ AppArmor profile loaded on $node"
    else
      log "⚠️  AppArmor profile not loaded on $node"
    fi
  done
}

check_falco() {
  log "Checking Falco deployment..."
  if kubectl get pods -n falco-system -l app=falco --no-headers | grep -q Running; then
    log "✓ Falco is running"
  else
    log "✗ ERROR: Falco is not running"
    return 1
  fi
}

check_pss_exceptions() {
  log "Checking PodSecurityStandards exceptions..."
  if kubectl get namespace mesh-network -o yaml | grep -q "pod-security.kubernetes.io/enforce: baseline"; then
    log "✓ PSS exceptions configured"
  else
    log "⚠️  PSS exceptions not found - applying"
    kubectl apply -f infra/k8s/pss-exceptions.yaml
  fi
}

main() {
  log "=== B.A.T.M.A.N. Deployment Prerequisites Check ==="
  check_node_pool || exit 1
  check_apparmor || true
  check_falco || exit 1
  check_pss_exceptions || true
  log "=== Prerequisites Check Complete ==="
}

main "$@"
