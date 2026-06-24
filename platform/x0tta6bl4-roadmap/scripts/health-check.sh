#!/usr/bin/env bash
set -euo pipefail
NS=${1:-mtls-demo}
echo "[x0tta6bl4] Health Check Namespace: $NS"
if ! command -v kubectl >/dev/null 2>&1; then
  echo "kubectl not found" >&2; exit 1; fi
kubectl get pods -n "$NS" || { echo "Failed to list pods"; exit 1; }
TOTAL=$(kubectl get pods -n "$NS" --no-headers 2>/dev/null | wc -l || echo 0)
RUNNING=$(kubectl get pods -n "$NS" --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l || echo 0)
PENDING=$(kubectl get pods -n "$NS" --field-selector=status.phase=Pending --no-headers 2>/dev/null | wc -l || echo 0)
echo "Total: $TOTAL | Running: $RUNNING | Pending: $PENDING"
if [ "$TOTAL" -gt 0 ] && [ "$RUNNING" -eq "$TOTAL" ]; then
  echo "✅ All pods running"
else
  echo "⌛ Waiting for full readiness"; fi
