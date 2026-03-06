#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME="${CLUSTER_NAME:-x0tta-dev}"
K8S_NAMESPACE="${K8S_NAMESPACE:-x0tta-system}"
HELM_RELEASE="${HELM_RELEASE:-mesh-op}"
SMOKE_NAMESPACE="${SMOKE_NAMESPACE:-mesh-op-smoke}"
SMOKE_NAME="${SMOKE_NAME:-smoke-reconcile}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-240}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info() {
  echo -e "${GREEN}[INFO]${NC}  $*"
}

warn() {
  echo -e "${YELLOW}[WARN]${NC}  $*"
}

error() {
  echo -e "${RED}[ERROR]${NC} $*" >&2
  exit 1
}

wait_resource_absent() {
  local namespace="$1"
  local resource="$2"
  local name="$3"
  local deadline=$((SECONDS + TIMEOUT_SECONDS))

  while (( SECONDS < deadline )); do
    if ! kubectl -n "$namespace" get "$resource" "$name" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done

  return 1
}

cleanup_smoke_namespace() {
  kubectl delete namespace "$SMOKE_NAMESPACE" --ignore-not-found=true --wait=false >/dev/null 2>&1 || true
}

trap cleanup_smoke_namespace EXIT

info "=== Preflight ==="
for bin in kind kubectl helm docker; do
  if ! command -v "$bin" >/dev/null 2>&1; then
    error "$bin not found in PATH"
  fi
done
docker info >/dev/null 2>&1 || error "docker daemon is not running"

info "=== Bootstrap operator stack in kind (${CLUSTER_NAME}) ==="
CLUSTER_NAME="$CLUSTER_NAME" \
K8S_NAMESPACE="$K8S_NAMESPACE" \
HELM_RELEASE="$HELM_RELEASE" \
"$REPO_ROOT/scripts/ops/bootstrap_k8s_dev.sh" \
  --cluster-name "$CLUSTER_NAME" \
  --release-name "$HELM_RELEASE"

info "=== Apply smoke MeshCluster (${SMOKE_NAMESPACE}/${SMOKE_NAME}) ==="
kubectl create namespace "$SMOKE_NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

cat <<EOF | kubectl -n "$SMOKE_NAMESPACE" apply -f -
apiVersion: x0tta6bl4.io/v1alpha1
kind: MeshCluster
metadata:
  name: ${SMOKE_NAME}
spec:
  replicas: 1
  trustDomain: smoke.mesh
  image:
    repository: x0tta6bl4/mesh-node
    tag: "3.4.0"
    pullPolicy: IfNotPresent
  pqc:
    enabled: false
EOF

kubectl -n "$SMOKE_NAMESPACE" wait \
  --for=jsonpath='{.status.phase}'=Running \
  "meshcluster/${SMOKE_NAME}" \
  "--timeout=${TIMEOUT_SECONDS}s"

kubectl -n "$SMOKE_NAMESPACE" get deployment "${SMOKE_NAME}-mesh" >/dev/null
kubectl -n "$SMOKE_NAMESPACE" get service "${SMOKE_NAME}-mesh" >/dev/null
kubectl -n "$SMOKE_NAMESPACE" get configmap "${SMOKE_NAME}-mesh-config" >/dev/null

info "=== Delete MeshCluster and verify finalizer cleanup ==="
kubectl -n "$SMOKE_NAMESPACE" delete "meshcluster/${SMOKE_NAME}" --wait=true "--timeout=${TIMEOUT_SECONDS}s"

wait_resource_absent "$SMOKE_NAMESPACE" deployment "${SMOKE_NAME}-mesh" \
  || error "deployment ${SMOKE_NAME}-mesh still exists after MeshCluster deletion"
wait_resource_absent "$SMOKE_NAMESPACE" service "${SMOKE_NAME}-mesh" \
  || error "service ${SMOKE_NAME}-mesh still exists after MeshCluster deletion"
wait_resource_absent "$SMOKE_NAMESPACE" configmap "${SMOKE_NAME}-mesh-config" \
  || error "configmap ${SMOKE_NAME}-mesh-config still exists after MeshCluster deletion"

info "Mesh operator kind e2e smoke passed."
