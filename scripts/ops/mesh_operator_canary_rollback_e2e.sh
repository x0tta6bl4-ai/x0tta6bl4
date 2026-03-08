#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME="${CLUSTER_NAME:-x0tta-dev}"
K8S_NAMESPACE="${K8S_NAMESPACE:-x0tta-system}"
HELM_RELEASE="${HELM_RELEASE:-mesh-op-canary}"
CHART_NAME="${CHART_NAME:-x0tta-mesh-operator}"
STABLE_IMAGE_REPO="${STABLE_IMAGE_REPO:-x0tta6bl4/mesh-operator}"
STABLE_IMAGE_TAG="${STABLE_IMAGE_TAG:-3.4.0}"
CANARY_IMAGE_TAG="${CANARY_IMAGE_TAG:-3.4.0-canary}"
CANARY_REPLICA_COUNT="${CANARY_REPLICA_COUNT:-2}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-300}"
MAX_ROLLBACK_SECONDS="${MAX_ROLLBACK_SECONDS:-600}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CHART_DIR="$REPO_ROOT/charts/x0tta-mesh-operator"
STABLE_IMAGE_REF="${STABLE_IMAGE_REPO}:${STABLE_IMAGE_TAG}"
CANARY_IMAGE_REF="${STABLE_IMAGE_REPO}:${CANARY_IMAGE_TAG}"

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

latest_revision() {
  helm history "$HELM_RELEASE" --namespace "$K8S_NAMESPACE" -o json | python3 -c '
import json
import sys

history = json.load(sys.stdin)
if not history:
    raise SystemExit(1)
print(history[-1]["revision"])
'
}

latest_status() {
  helm history "$HELM_RELEASE" --namespace "$K8S_NAMESPACE" -o json | python3 -c '
import json
import sys

history = json.load(sys.stdin)
if not history:
    raise SystemExit(1)
print(history[-1]["status"])
'
}

cleanup() {
  helm -n "$K8S_NAMESPACE" uninstall "$HELM_RELEASE" >/dev/null 2>&1 || true
}
trap cleanup EXIT

if [[ "$CANARY_IMAGE_TAG" == "$STABLE_IMAGE_TAG" ]]; then
  error "CANARY_IMAGE_TAG must differ from STABLE_IMAGE_TAG"
fi

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

info "=== Install stable release ==="
INSTALL_CRDS_VALUE="1"
if kubectl get customresourcedefinition meshclusters.x0tta6bl4.io >/dev/null 2>&1; then
  info "CRD meshclusters.x0tta6bl4.io already exists -> installCRDs=0 for this release"
  INSTALL_CRDS_VALUE="0"
fi

CLUSTER_NAME="$CLUSTER_NAME" \
K8S_NAMESPACE="$K8S_NAMESPACE" \
HELM_RELEASE="$HELM_RELEASE" \
IMAGE_REPO="$STABLE_IMAGE_REPO" \
IMAGE_TAG="$STABLE_IMAGE_TAG" \
INSTALL_CRDS="$INSTALL_CRDS_VALUE" \
SKIP_DEMO_CR=1 \
"$REPO_ROOT/scripts/ops/bootstrap_k8s_dev.sh" \
  --cluster-name "$CLUSTER_NAME" \
  --release-name "$HELM_RELEASE"

python3 "$REPO_ROOT/scripts/ops/mesh_operator_health.py" smoke \
  --namespace "$K8S_NAMESPACE" \
  --release "$HELM_RELEASE" \
  --wait-seconds "$TIMEOUT_SECONDS"

stable_revision="$(latest_revision)"
stable_replicas="$(kubectl -n "$K8S_NAMESPACE" get deployment "$OPERATOR_FULLNAME" -o jsonpath='{.spec.replicas}')"
stable_image_actual="$(kubectl -n "$K8S_NAMESPACE" get deployment "$OPERATOR_FULLNAME" -o jsonpath='{.spec.template.spec.containers[?(@.name=="manager")].image}')"

[[ "$stable_image_actual" == "$STABLE_IMAGE_REF" ]] \
  || error "stable image mismatch: expected ${STABLE_IMAGE_REF}, got ${stable_image_actual}"

info "Stable revision: ${stable_revision}, replicas: ${stable_replicas}, image: ${stable_image_actual}"

info "=== Prepare canary image tag ==="
docker image inspect "$STABLE_IMAGE_REF" >/dev/null 2>&1 \
  || error "stable image not found locally: ${STABLE_IMAGE_REF}"
docker tag "$STABLE_IMAGE_REF" "$CANARY_IMAGE_REF"
kind load docker-image "$CANARY_IMAGE_REF" --name "$CLUSTER_NAME" >/dev/null
info "Canary image loaded into kind/${CLUSTER_NAME}: ${CANARY_IMAGE_REF}"

info "=== Canary rollout ==="
helm upgrade "$HELM_RELEASE" "$CHART_DIR" \
  --namespace "$K8S_NAMESPACE" \
  --reuse-values \
  --set "operator.image.repository=${STABLE_IMAGE_REPO}" \
  --set "operator.image.tag=${CANARY_IMAGE_TAG}" \
  --set "operator.image.pullPolicy=IfNotPresent" \
  --set "operator.replicaCount=${CANARY_REPLICA_COUNT}" \
  --wait \
  --timeout "${TIMEOUT_SECONDS}s"

kubectl -n "$K8S_NAMESPACE" rollout status \
  "deployment/${OPERATOR_FULLNAME}" \
  "--timeout=${TIMEOUT_SECONDS}s"

canary_image_actual="$(kubectl -n "$K8S_NAMESPACE" get deployment "$OPERATOR_FULLNAME" -o jsonpath='{.spec.template.spec.containers[?(@.name=="manager")].image}')"
canary_replicas_actual="$(kubectl -n "$K8S_NAMESPACE" get deployment "$OPERATOR_FULLNAME" -o jsonpath='{.spec.replicas}')"

[[ "$canary_image_actual" == "$CANARY_IMAGE_REF" ]] \
  || error "canary image mismatch: expected ${CANARY_IMAGE_REF}, got ${canary_image_actual}"
[[ "$canary_replicas_actual" == "$CANARY_REPLICA_COUNT" ]] \
  || error "canary replicas mismatch: expected ${CANARY_REPLICA_COUNT}, got ${canary_replicas_actual}"

info "=== Rollback to stable revision ${stable_revision} ==="
rollback_started_epoch="$(date +%s)"
helm rollback "$HELM_RELEASE" "$stable_revision" \
  --namespace "$K8S_NAMESPACE" \
  --wait \
  --timeout "${TIMEOUT_SECONDS}s"
kubectl -n "$K8S_NAMESPACE" rollout status \
  "deployment/${OPERATOR_FULLNAME}" \
  "--timeout=${TIMEOUT_SECONDS}s"
rollback_ended_epoch="$(date +%s)"
rollback_seconds="$((rollback_ended_epoch - rollback_started_epoch))"

post_rollback_image="$(kubectl -n "$K8S_NAMESPACE" get deployment "$OPERATOR_FULLNAME" -o jsonpath='{.spec.template.spec.containers[?(@.name=="manager")].image}')"
post_rollback_replicas="$(kubectl -n "$K8S_NAMESPACE" get deployment "$OPERATOR_FULLNAME" -o jsonpath='{.spec.replicas}')"
post_rollback_status="$(latest_status)"

[[ "$post_rollback_image" == "$STABLE_IMAGE_REF" ]] \
  || error "rollback image mismatch: expected ${STABLE_IMAGE_REF}, got ${post_rollback_image}"
[[ "$post_rollback_replicas" == "$stable_replicas" ]] \
  || error "rollback replicas mismatch: expected ${stable_replicas}, got ${post_rollback_replicas}"
[[ "$post_rollback_status" == "deployed" ]] \
  || error "helm latest revision status is ${post_rollback_status}, expected deployed"

if (( rollback_seconds > MAX_ROLLBACK_SECONDS )); then
  error "rollback took ${rollback_seconds}s, exceeds max ${MAX_ROLLBACK_SECONDS}s"
fi

info "Canary rollout + rollback e2e passed."
info "Rollback duration: ${rollback_seconds}s (max ${MAX_ROLLBACK_SECONDS}s)"
info "Final image: ${post_rollback_image}; replicas: ${post_rollback_replicas}"
