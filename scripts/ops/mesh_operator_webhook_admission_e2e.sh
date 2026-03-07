#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME="${CLUSTER_NAME:-x0tta-dev}"
K8S_NAMESPACE="${K8S_NAMESPACE:-x0tta-system}"
HELM_RELEASE="${HELM_RELEASE:-mesh-op}"
CHART_NAME="${CHART_NAME:-x0tta-mesh-operator}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-300}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

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

EXISTING_RELEASE_NAMESPACE="$(helm list -A 2>/dev/null | awk -v rel="$HELM_RELEASE" 'NR>1 && $1==rel {print $2; exit}')"
if [[ -n "$EXISTING_RELEASE_NAMESPACE" && "$EXISTING_RELEASE_NAMESPACE" != "$K8S_NAMESPACE" ]]; then
  info "Helm release ${HELM_RELEASE} already exists in ${EXISTING_RELEASE_NAMESPACE}; overriding namespace ${K8S_NAMESPACE} -> ${EXISTING_RELEASE_NAMESPACE}"
  K8S_NAMESPACE="$EXISTING_RELEASE_NAMESPACE"
fi

OPERATOR_FULLNAME="$HELM_RELEASE"
if [[ "$HELM_RELEASE" != *"$CHART_NAME"* ]]; then
  OPERATOR_FULLNAME="${HELM_RELEASE}-${CHART_NAME}"
fi
WEBHOOK_SERVICE="${OPERATOR_FULLNAME}-webhook-service"
WEBHOOK_TLS_SECRET="${HELM_RELEASE}-webhook-manual-tls"
INVALID_NAME="webhook-invalid"
MINIMAL_NAME="webhook-minimal"

TMP_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "$TMP_DIR"
  kubectl -n "$K8S_NAMESPACE" delete meshcluster "$MINIMAL_NAME" --ignore-not-found=true >/dev/null 2>&1 || true
}
trap cleanup EXIT

info "Preparing manual TLS for webhook service ${WEBHOOK_SERVICE}.${K8S_NAMESPACE}.svc"
cat >"$TMP_DIR/openssl.cnf" <<EOF
[ req ]
default_bits       = 2048
prompt             = no
default_md         = sha256
distinguished_name = dn
x509_extensions    = v3_req

[ dn ]
CN = ${WEBHOOK_SERVICE}.${K8S_NAMESPACE}.svc

[ v3_req ]
subjectAltName = @alt_names

[ alt_names ]
DNS.1 = ${WEBHOOK_SERVICE}
DNS.2 = ${WEBHOOK_SERVICE}.${K8S_NAMESPACE}.svc
DNS.3 = ${WEBHOOK_SERVICE}.${K8S_NAMESPACE}.svc.cluster.local
EOF

openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout "$TMP_DIR/tls.key" \
  -out "$TMP_DIR/tls.crt" \
  -config "$TMP_DIR/openssl.cnf" >/dev/null 2>&1

kubectl -n "$K8S_NAMESPACE" create secret tls "$WEBHOOK_TLS_SECRET" \
  --cert="$TMP_DIR/tls.crt" \
  --key="$TMP_DIR/tls.key" \
  --dry-run=client -o yaml | kubectl apply -f - >/dev/null

WEBHOOK_CA_BUNDLE="$(base64 -w0 <"$TMP_DIR/tls.crt")"

info "Enabling mesh-operator webhooks via bootstrap"
CLUSTER_NAME="$CLUSTER_NAME" \
K8S_NAMESPACE="$K8S_NAMESPACE" \
HELM_RELEASE="$HELM_RELEASE" \
ENABLE_WEBHOOKS=1 \
WEBHOOK_CERT_MANAGER_ENABLED=0 \
WEBHOOK_TLS_SECRET_NAME="$WEBHOOK_TLS_SECRET" \
WEBHOOK_TLS_CA_BUNDLE="$WEBHOOK_CA_BUNDLE" \
"$REPO_ROOT/scripts/ops/bootstrap_k8s_dev.sh" \
  --cluster-name "$CLUSTER_NAME" \
  --release-name "$HELM_RELEASE"

kubectl get validatingwebhookconfiguration "${OPERATOR_FULLNAME}-validating" >/dev/null
kubectl get mutatingwebhookconfiguration "${OPERATOR_FULLNAME}-mutating" >/dev/null

info "Checking reject path for invalid MeshCluster"
cat >"$TMP_DIR/invalid.yaml" <<EOF
apiVersion: x0tta6bl4.io/v1alpha1
kind: MeshCluster
metadata:
  name: ${INVALID_NAME}
  namespace: ${K8S_NAMESPACE}
spec:
  replicas: 2000
EOF

if kubectl apply -f "$TMP_DIR/invalid.yaml" >"$TMP_DIR/invalid.out" 2>"$TMP_DIR/invalid.err"; then
  cat "$TMP_DIR/invalid.out" >&2
  error "invalid MeshCluster was accepted, expected reject from validating webhook"
fi

if ! grep -Ei "invalid|Unsupported value|spec|must be between" "$TMP_DIR/invalid.err" >/dev/null; then
  cat "$TMP_DIR/invalid.err" >&2
  error "invalid MeshCluster was rejected, but error message did not contain validation details"
fi

info "Checking defaulting path for minimal MeshCluster"
cat >"$TMP_DIR/minimal.yaml" <<EOF
apiVersion: x0tta6bl4.io/v1alpha1
kind: MeshCluster
metadata:
  name: ${MINIMAL_NAME}
  namespace: ${K8S_NAMESPACE}
spec: {}
EOF

kubectl apply -f "$TMP_DIR/minimal.yaml" >/dev/null

replicas="$(kubectl -n "$K8S_NAMESPACE" get meshcluster "$MINIMAL_NAME" -o jsonpath='{.spec.replicas}')"
trust_domain="$(kubectl -n "$K8S_NAMESPACE" get meshcluster "$MINIMAL_NAME" -o jsonpath='{.spec.trustDomain}')"
image_repo="$(kubectl -n "$K8S_NAMESPACE" get meshcluster "$MINIMAL_NAME" -o jsonpath='{.spec.image.repository}')"
image_tag="$(kubectl -n "$K8S_NAMESPACE" get meshcluster "$MINIMAL_NAME" -o jsonpath='{.spec.image.tag}')"
pull_policy="$(kubectl -n "$K8S_NAMESPACE" get meshcluster "$MINIMAL_NAME" -o jsonpath='{.spec.image.pullPolicy}')"
bridge_chain_id="$(kubectl -n "$K8S_NAMESPACE" get meshcluster "$MINIMAL_NAME" -o jsonpath='{.spec.dao.bridge.chainId}')"

[[ "$replicas" == "3" ]] || error "default replicas mismatch: got $replicas"
[[ "$trust_domain" == "x0tta6bl4.mesh" ]] || error "default trustDomain mismatch: got $trust_domain"
[[ "$image_repo" == "x0tta6bl4/mesh-node" ]] || error "default image.repository mismatch: got $image_repo"
[[ "$image_tag" == "3.4.0" ]] || error "default image.tag mismatch: got $image_tag"
[[ "$pull_policy" == "IfNotPresent" ]] || error "default image.pullPolicy mismatch: got $pull_policy"
[[ "$bridge_chain_id" == "84532" ]] || error "default dao.bridge.chainId mismatch: got $bridge_chain_id"

kubectl -n "$K8S_NAMESPACE" delete meshcluster "$MINIMAL_NAME" --wait=true "--timeout=${TIMEOUT_SECONDS}s" >/dev/null

info "Webhook admission e2e passed."
