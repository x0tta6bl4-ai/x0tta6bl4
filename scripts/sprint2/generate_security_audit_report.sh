#!/bin/bash
# scripts/sprint2/generate_security_audit_report.sh
set -euo pipefail

REPORT_FILE="security_audit_$(date +%Y%m%d_%H%M%S).md"

log() { echo "[$(date -Iseconds)] $*" >&2; }

generate_report() {
cat > "$REPORT_FILE" << 'EOF'
Security Audit Report
Generated: $(date -Iseconds)

Node Pool Configuration
-----------------------
Privileged Nodes

$(kubectl get nodes -l batman-adv-capable=true -o wide)

Node Taints

$(for node in $(kubectl get nodes -l batman-adv-capable=true -o name); do
  echo "=== $node ==="
  kubectl get $node -o json | jq -r '.spec.taints[]? // empty'
  echo ""
done)

AppArmor Status
---------------
$(for node in $(kubectl get nodes -l batman-adv-capable=true -o jsonpath='{.items[*].metadata.name}'); do
  echo "=== $node ==="
  kubectl debug node/$node -it --image=ubuntu:22.04 -- aa-status 2>&1 | grep -A 10 batman-adv || echo "Profile not loaded"
  echo ""
done)

Falco Security Events (Last 24h)
--------------------------------
Critical Events

$(kubectl logs -n falco-system -l app=falco --since=24h | grep -c "priority=Critical") critical events detected

Warning Events

$(kubectl logs -n falco-system -l app=falco --since=24h | grep -c "priority=Warning") warning events detected

Top 10 Most Common Events

$(kubectl logs -n falco-system -l app=falco --since=24h | grep "rule=" | sed 's/.*rule=\([^ ]*\).*/\1/' | sort | uniq -c | sort -rn | head -10)

B.A.T.M.A.N. Deployment Status
------------------------------
Pods

$(kubectl get pods -n mesh-network -o wide)

Network Connectivity

$(for pod in $(kubectl get pods -n mesh-network -l app=batman-adv-gateway -o name); do
  echo "=== $pod ==="
  kubectl exec -n mesh-network $pod -c batman-adv -- batctl o 2>&1
  echo ""
done)

Recommendations
---------------
$(
errors=0
critical_count=$(kubectl logs -n falco-system -l app=falco --since=24h | grep -c "priority=Critical")
if [[ ${critical_count:-0} -gt 0 ]]; then
  echo "- ⚠️ CRITICAL: $critical_count critical security events detected - review immediately"
  errors=$((errors + 1))
fi
privileged_count=$(kubectl get pods -n mesh-network -o json | jq -r '.items[].spec.containers[]? | select(.securityContext.privileged==true) | .name' | wc -l | tr -d ' ')
if [[ ${privileged_count:-0} -gt 3 ]]; then
  echo "- ⚠️ WARNING: $privileged_count containers running privileged (expected: 3)"
  errors=$((errors + 1))
fi
for pod in $(kubectl get pods -n mesh-network -l app=batman-adv-gateway -o name); do
  peer_count=$(kubectl exec -n mesh-network $pod -c batman-adv -- batctl o 2>/dev/null | wc -l | tr -d ' ')
  if [[ ${peer_count:-0} -lt 2 ]]; then
    echo "- ⚠️ WARNING: $pod has insufficient peers ($peer_count) - check mesh connectivity"
    errors=$((errors + 1))
  fi
  done
if [[ $errors -eq 0 ]]; then
  echo "- ✅ All checks passed - security posture is healthy"
fi
)

Next Steps
----------
- Review critical security events in detail
- Validate mesh network performance (latency/throughput)
- Conduct penetration testing on privileged workloads
- Schedule next audit in 7 days
EOF
}

main() {
  log "Generating security audit report..."
  generate_report
  log "Report saved to: $REPORT_FILE"
  log "View with: cat $REPORT_FILE"
}

main "$@"
