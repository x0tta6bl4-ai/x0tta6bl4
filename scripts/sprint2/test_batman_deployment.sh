#!/bin/bash
# scripts/sprint2/test_batman_deployment.sh
set -euo pipefail

log() { echo "[$(date -Iseconds)] $*" >&2; }

test_module_loaded() {
  log "Testing batman_adv module..."
  for pod in $(kubectl get pods -n mesh-network -l app=batman-adv-gateway -o name); do
    if kubectl exec -n mesh-network "$pod" -c batman-adv -- lsmod | grep -q batman_adv; then
      log "✓ batman_adv module loaded in $pod"
    else
      log "✗ ERROR: batman_adv module not loaded in $pod"; return 1
    fi
  done
}

test_interface_created() {
  log "Testing bat0 interface..."
  for pod in $(kubectl get pods -n mesh-network -l app=batman-adv-gateway -o name); do
    if kubectl exec -n mesh-network "$pod" -c batman-adv -- batctl if | grep -q bat0; then
      log "✓ bat0 interface created in $pod"
    else
      log "✗ ERROR: bat0 interface not found in $pod"; return 1
    fi
  done
}

test_mesh_formation() {
  log "Testing mesh network formation..."
  for pod in $(kubectl get pods -n mesh-network -l app=batman-adv-gateway -o name); do
    peer_count=$(kubectl exec -n mesh-network "$pod" -c batman-adv -- batctl o | wc -l | tr -d ' ')
    log "Info: $pod sees $peer_count peers"
  done
}

test_metrics_export() {
  log "Testing metrics export..."
  for pod in $(kubectl get pods -n mesh-network -l app=batman-adv-gateway -o name); do
    if kubectl exec -n mesh-network "$pod" -c exporter -- curl -s http://localhost:9100/metrics | grep -q batman; then
      log "✓ Metrics exported from $pod"
    else
      log "✗ ERROR: Metrics not available from $pod"; return 1
    fi
  done
}

test_falco_monitoring() {
  log "Testing Falco monitoring..."
  kubectl exec -n mesh-network batman-adv-gateway-0 -c batman-adv -- /bin/bash -c "echo test" 2>&1 || true
  sleep 5
  if kubectl logs -n falco-system -l app=falco --tail=200 | grep -q "Shell spawned in privileged batman-adv pod"; then
    log "✓ Falco detected shell spawn (expected)"
  else
    log "⚠️  WARNING: Falco did not detect shell spawn"
  fi
}

main() {
  log "=== B.A.T.M.A.N. Deployment Validation ==="
  test_module_loaded || exit 1
  test_interface_created || exit 1
  test_mesh_formation || true
  test_metrics_export || exit 1
  test_falco_monitoring || true
  log "=== Validation Complete ==="
}

main "$@"
