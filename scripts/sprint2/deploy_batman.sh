#!/bin/bash
# scripts/sprint2/deploy_batman.sh
set -euo pipefail

log() { echo "[$(date -Iseconds)] $*" >&2; }

log "=== Deploying B.A.T.M.A.N. Advanced ==="

bash scripts/sprint2/validate_batman_prerequisites.sh || exit 1

log "Applying PodSecurityStandards exceptions..."
kubectl apply -f infra/k8s/pss-exceptions.yaml

log "Deploying B.A.T.M.A.N. Helm chart..."
helm upgrade --install batman-adv \
  infra/networking/batman-adv/helm-charts/batman-adv-optimization \
  -n mesh-network \
  --create-namespace \
  --values infra/networking/batman-adv/helm-charts/batman-adv-optimization/values-production.yaml \
  --wait \
  --timeout 10m

log "Waiting for B.A.T.M.A.N. pods to be ready..."
kubectl wait --for=condition=Ready pods -l app=batman-adv-gateway -n mesh-network --timeout=600s || true

log "Verifying B.A.T.M.A.N. deployment..."
kubectl get pods -n mesh-network -o wide

log "=== B.A.T.M.A.N. Deployment Complete ==="
