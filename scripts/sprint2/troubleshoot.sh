#!/bin/bash
# scripts/sprint2/troubleshoot.sh
set -euo pipefail

log() {
    echo "[$(date -Iseconds)] $*"
}

check_node_pool() {
    log "Checking node pool status..."
    node_count=$(kubectl get nodes -l batman-adv-capable=true --no-headers 2>/dev/null | wc -l | tr -d ' ')
    if [[ ${node_count:-0} -lt 3 ]]; then
        log "ERROR: Insufficient batman-adv-capable nodes (found: $node_count, required: 3)"
        log "Fix: Re-run node pool setup script"
        return 1
    fi
    log "✓ Node pool OK ($node_count nodes)"
}

check_apparmor() {
    log "Checking AppArmor profiles..."
    for node in $(kubectl get nodes -l batman-adv-capable=true -o jsonpath='{.items[*].metadata.name}'); do
        if kubectl debug node/"$node" -it --image=ubuntu:22.04 -- aa-status 2>&1 | grep -q batman-adv-profile; then
            log "✓ AppArmor profile OK on $node"
        else
            log "WARNING: AppArmor profile missing on $node"
            log "Fix: bash scripts/sprint2/deploy_apparmor_profiles.sh"
        fi
    done
}

check_falco() {
    log "Checking Falco deployment..."
    if ! kubectl get pods -n falco-system -l app=falco --no-headers 2>/dev/null | grep -q Running; then
        log "ERROR: Falco not running"
        log "Fix: bash scripts/sprint2/deploy_falco.sh"
        log "Debug: kubectl logs -n falco-system -l app=falco"
        return 1
    fi
    log "✓ Falco OK"
}

check_batman() {
    log "Checking B.A.T.M.A.N. deployment..."
    if ! kubectl get pods -n mesh-network -l app=batman-adv-gateway --no-headers 2>/dev/null | grep -q Running; then
        log "ERROR: B.A.T.M.A.N. pods not running"
        log "Fix: bash scripts/sprint2/deploy_batman.sh"
        log "Debug: kubectl logs -n mesh-network -l app=batman-adv-gateway"
        return 1
    fi
    for pod in $(kubectl get pods -n mesh-network -l app=batman-adv-gateway -o name); do
        if ! kubectl exec -n mesh-network "$pod" -c batman-adv -- lsmod 2>/dev/null | grep -q batman_adv; then
            log "WARNING: batman_adv module not loaded in $pod"
            log "Fix: kubectl delete $pod -n mesh-network"
        fi
    done
    log "✓ B.A.T.M.A.N. OK"
}

check_mesh_connectivity() {
    log "Checking mesh network connectivity..."
    for pod in $(kubectl get pods -n mesh-network -l app=batman-adv-gateway -o name); do
        peer_count=$(kubectl exec -n mesh-network "$pod" -c batman-adv -- batctl o 2>/dev/null | wc -l | tr -d ' ')
        if [[ ${peer_count:-0} -lt 2 ]]; then
            log "WARNING: $pod has insufficient peers ($peer_count)"
            log "Expected: >= 2 peers"
        else
            log "✓ $pod mesh connectivity OK ($peer_count peers)"
        fi
    done
}

fix_common_issues() {
    log "Attempting to fix common issues..."
    if ! kubectl get pods -n falco-system -l app=falco --no-headers | grep -q Running; then
        log "Restarting Falco..."
        kubectl rollout restart daemonset/falco -n falco-system
        kubectl rollout status daemonset/falco -n falco-system --timeout=300s || true
    fi
    for pod in $(kubectl get pods -n mesh-network -l app=batman-adv-gateway -o name); do
        if ! kubectl exec -n mesh-network "$pod" -c batman-adv -- lsmod 2>/dev/null | grep -q batman_adv; then
            log "Restarting $pod to reload module..."
            kubectl delete "$pod" -n mesh-network
        fi
    done
    log "Waiting for pods to restart..."
    sleep 30
}

main() {
    log "=== Sprint 2 Troubleshooting ==="
    errors=0
    check_node_pool || errors=$((errors + 1))
    check_apparmor || true
    check_falco || errors=$((errors + 1))
    check_batman || errors=$((errors + 1))
    check_mesh_connectivity || true
    if [[ $errors -gt 0 ]]; then
        log ""; log "Found $errors critical issues"; log "Attempting automatic fixes..."
        fix_common_issues
        log ""; log "Re-running checks..."
        check_falco || true
        check_batman || true
        check_mesh_connectivity || true
    fi
    log ""; log "=== Troubleshooting Complete ==="
}

main "$@"
