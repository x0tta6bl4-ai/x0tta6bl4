#!/bin/bash
# scripts/sprint2/quick_deploy_self_managed.sh
set -euo pipefail

export NODES=${NODES:-"node-1 node-2 node-3"}

echo "=== Self-Managed Quick Deploy ==="
bash scripts/sprint2/setup_privileged_nodes_self_managed.sh
bash scripts/sprint2/validate_node_pool.sh
bash scripts/sprint2/deploy_apparmor_profiles.sh || true
bash scripts/sprint2/deploy_falco.sh
kubectl apply -f monitoring/falco/falco-exporter-deployment.yaml || true
bash scripts/sprint2/validate_batman_prerequisites.sh
bash scripts/sprint2/deploy_batman.sh
bash scripts/sprint2/test_batman_deployment.sh || true
bash scripts/sprint2/generate_security_audit_report.sh

echo "✅ Self-managed deployment complete. Monitor: bash scripts/sprint2/monitor_security_events.sh"
