#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME="${CLUSTER_NAME:-x0tta-dev}"
K8S_NAMESPACE="${K8S_NAMESPACE:-x0tta-system}"
HELM_RELEASE="${HELM_RELEASE:-mesh-op-lifecycle}"
CHART_NAME="${CHART_NAME:-x0tta-mesh-operator}"
UPGRADE_REPLICA_COUNT="${UPGRADE_REPLICA_COUNT:-2}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-300}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CHART_DIR="$REPO_ROOT/charts/x0tta-mesh-operator"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

info() {
  echo -e "${GREEN}[INFO]${NC}  $*"
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

wait_cluster_resource_absent() {
  local resource="$1"
  local name="$2"
  local deadline=$((SECONDS + TIMEOUT_SECONDS))

  while (( SECONDS < deadline )); do
    if ! kubectl get "$resource" "$name" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done

  return 1
}

cleanup() {
  helm -n "$K8S_NAMESPACE" uninstall "$HELM_RELEASE" >/dev/null 2>&1 || true
}
trap cleanup EXIT

OPERATOR_FULLNAME="$HELM_RELEASE"
if [[ "$HELM_RELEASE" != *"$CHART_NAME"* ]]; then
  OPERATOR_FULLNAME="${HELM_RELEASE}-${CHART_NAME}"
fi

info "=== Preflight ==="
for bin in kind kubectl helm docker python3; do
  if ! command -v "$bin" >/dev/null 2>&1; then
    error "$bin not found in PATH"
  fi
done
docker info >/dev/null 2>&1 || error "docker daemon is not running"

info "=== Install (helm upgrade --install) ==="
INSTALL_CRDS_VALUE="1"
if kubectl get customresourcedefinition meshclusters.x0tta6bl4.io >/dev/null 2>&1; then
  info "CRD meshclusters.x0tta6bl4.io already exists -> installCRDs=0 for this release"
  INSTALL_CRDS_VALUE="0"
fi

CLUSTER_NAME="$CLUSTER_NAME" \
K8S_NAMESPACE="$K8S_NAMESPACE" \
HELM_RELEASE="$HELM_RELEASE" \
INSTALL_CRDS="$INSTALL_CRDS_VALUE" \
SKIP_DEMO_CR=1 \
"$REPO_ROOT/scripts/ops/bootstrap_k8s_dev.sh" \
  --cluster-name "$CLUSTER_NAME" \
  --release-name "$HELM_RELEASE"

python3 "$REPO_ROOT/scripts/ops/mesh_operator_health.py" smoke \
  --namespace "$K8S_NAMESPACE" \
  --release "$HELM_RELEASE" \
  --wait-seconds "$TIMEOUT_SECONDS"

info "=== Upgrade (replica count mutation) ==="
helm upgrade "$HELM_RELEASE" "$CHART_DIR" \
  --namespace "$K8S_NAMESPACE" \
  --reuse-values \
  --set "operator.replicaCount=${UPGRADE_REPLICA_COUNT}" \
  --wait \
  --timeout "${TIMEOUT_SECONDS}s"

kubectl -n "$K8S_NAMESPACE" rollout status \
  "deployment/${OPERATOR_FULLNAME}" \
  "--timeout=${TIMEOUT_SECONDS}s"

actual_replicas="$(kubectl -n "$K8S_NAMESPACE" get deployment "$OPERATOR_FULLNAME" -o jsonpath='{.spec.replicas}')"
[[ "$actual_replicas" == "$UPGRADE_REPLICA_COUNT" ]] \
  || error "upgrade replicas mismatch: expected ${UPGRADE_REPLICA_COUNT}, got ${actual_replicas}"

info "=== Uninstall ==="
helm uninstall "$HELM_RELEASE" --namespace "$K8S_NAMESPACE"

if helm status "$HELM_RELEASE" --namespace "$K8S_NAMESPACE" >/dev/null 2>&1; then
  error "helm release ${HELM_RELEASE} still exists after uninstall"
fi

wait_resource_absent "$K8S_NAMESPACE" deployment "$OPERATOR_FULLNAME" \
  || error "deployment ${OPERATOR_FULLNAME} still exists after uninstall"
wait_resource_absent "$K8S_NAMESPACE" service "${OPERATOR_FULLNAME}-metrics" \
  || error "service ${OPERATOR_FULLNAME}-metrics still exists after uninstall"
wait_resource_absent "$K8S_NAMESPACE" serviceaccount "$OPERATOR_FULLNAME" \
  || error "serviceaccount ${OPERATOR_FULLNAME} still exists after uninstall"

wait_cluster_resource_absent clusterrole "${OPERATOR_FULLNAME}-manager" \
  || error "clusterrole ${OPERATOR_FULLNAME}-manager still exists after uninstall"
wait_cluster_resource_absent clusterrolebinding "${OPERATOR_FULLNAME}-manager" \
  || error "clusterrolebinding ${OPERATOR_FULLNAME}-manager still exists after uninstall"

if [[ "$INSTALL_CRDS_VALUE" == "1" ]]; then
  wait_cluster_resource_absent customresourcedefinition meshclusters.x0tta6bl4.io \
    || error "CRD meshclusters.x0tta6bl4.io still exists after uninstall"
else
  info "CRD cleanup check skipped (CRD was pre-existing and not owned by this release)"
fi

info "Mesh operator Helm lifecycle e2e passed."
