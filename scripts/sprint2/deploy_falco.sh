#!/bin/bash
# scripts/sprint2/deploy_falco.sh
set -euo pipefail

log() { echo "[$(date -Iseconds)] $*" >&2; }

log "=== Deploying Falco Runtime Security ==="
helm repo add falcosecurity https://falcosecurity.github.io/charts
helm repo update

helm install falco falcosecurity/falco \
  -n falco-system \
  --create-namespace \
  --set falco.grpc.enabled=true \
  --set falco.grpcOutput.enabled=true \
  --set falco.httpOutput.enabled=true \
  --set ebpf.enabled=true \
  --set driver.kind=ebpf \
  --wait

log "Waiting for Falco pods to be ready..."
kubectl wait --for=condition=Ready pods -l app=falco -n falco-system --timeout=300s || true

log "Applying custom Falco rules..."
kubectl create configmap falco-rules-batman \
  --from-file=monitoring/falco/falco-rules-batman-adv.yaml \
  -n falco-system \
  --dry-run=client -o yaml | kubectl apply -f -

log "Restarting Falco to load custom rules..."
kubectl rollout restart daemonset/falco -n falco-system
kubectl rollout status daemonset/falco -n falco-system --timeout=300s || true

log "=== Falco Deployment Complete ==="
