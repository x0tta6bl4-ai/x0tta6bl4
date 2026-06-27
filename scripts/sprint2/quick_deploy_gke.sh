#!/bin/bash
# scripts/sprint2/quick_deploy_gke.sh
set -euo pipefail

export CLUSTER_NAME=${CLUSTER_NAME:-mesh-production}
export ZONE=${ZONE:-us-central1-a}
export MACHINE_TYPE=${MACHINE_TYPE:-n1-standard-2}
export MIN_NODES=${MIN_NODES:-3}
export MAX_NODES=${MAX_NODES:-5}

echo "=== GKE Quick Deploy ==="
bash scripts/sprint2/setup_privileged_node_pool_gke.sh
bash scripts/sprint2/validate_node_pool.sh
bash scripts/sprint2/deploy_apparmor_profiles.sh || true
bash scripts/sprint2/deploy_falco.sh
kubectl apply -f monitoring/falco/falco-exporter-deployment.yaml || true
bash scripts/sprint2/validate_batman_prerequisites.sh
bash scripts/sprint2/deploy_batman.sh
bash scripts/sprint2/test_batman_deployment.sh || true
bash scripts/sprint2/generate_security_audit_report.sh

echo "✅ GKE deployment complete. Monitor: bash scripts/sprint2/monitor_security_events.sh"
