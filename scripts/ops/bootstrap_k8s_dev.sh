#!/usr/bin/env bash
# =============================================================================
# bootstrap_k8s_dev.sh — x0tta6bl4 local K8s dev cluster
# =============================================================================
# Creates a kind cluster, installs x0tta-mesh-operator via Helm, applies a
# demo MeshCluster CR, and verifies the stack is healthy.
#
# Prerequisites (all present in this environment):
#   kind v0.20+, kubectl, helm v3+, docker
#
# Usage:
#   ./scripts/ops/bootstrap_k8s_dev.sh [--cluster-name NAME] [--release-name NAME]
#                                       [--skip-build] [--dao-gov-addr 0x...] [--dao-tok-addr 0x...]
#
# Env overrides:
#   CLUSTER_NAME        kind cluster name         (default: x0tta-dev)
#   K8S_NAMESPACE       operator namespace         (default: x0tta-system)
#   HELM_RELEASE        Helm release name          (default: mesh-op)
#   IMAGE_REPO          mesh-operator repository   (default: x0tta6bl4/mesh-operator)
#   IMAGE_TAG           mesh-operator image tag    (default: 3.4.0)
#   MESH_NODE_IMAGE_REPO mesh-node repository      (default: x0tta6bl4/mesh-node)
#   MESH_NODE_IMAGE_TAG  mesh-node image tag       (default: 3.4.0)
#   BASE_SEPOLIA_RPC    DAO RPC endpoint           (default: https://sepolia.base.org)
#   GOV_ADDRESS         MeshGovernance address     (default: "")
#   TOK_ADDRESS         X0TToken address           (default: "")
#   ENABLE_WEBHOOKS     enable admission webhooks  (default: 0)
#   WEBHOOK_CERT_MANAGER_ENABLED use cert-manager  (default: 0)
#   WEBHOOK_TLS_SECRET_NAME webhook TLS secret name (default: "")
#   WEBHOOK_TLS_CA_BUNDLE webhook CA bundle b64     (default: "")
#   INSTALL_CRDS        set to "0" to skip CRD install (default: 1)
#   SKIP_DEMO_CR        set to "1" to skip applying demo MeshCluster
#   SKIP_KIND_CREATE    set to "1" to reuse existing cluster
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
CLUSTER_NAME="${CLUSTER_NAME:-x0tta-dev}"
K8S_NAMESPACE="${K8S_NAMESPACE:-x0tta-system}"
HELM_RELEASE="${HELM_RELEASE:-mesh-op}"
IMAGE_REPO="${IMAGE_REPO:-x0tta6bl4/mesh-operator}"
IMAGE_TAG="${IMAGE_TAG:-3.4.0}"
MESH_NODE_IMAGE_REPO="${MESH_NODE_IMAGE_REPO:-x0tta6bl4/mesh-node}"
MESH_NODE_IMAGE_TAG="${MESH_NODE_IMAGE_TAG:-3.4.0}"
BASE_SEPOLIA_RPC="${BASE_SEPOLIA_RPC:-https://sepolia.base.org}"
GOV_ADDRESS="${GOV_ADDRESS:-}"
TOK_ADDRESS="${TOK_ADDRESS:-}"
ENABLE_WEBHOOKS="${ENABLE_WEBHOOKS:-0}"
WEBHOOK_CERT_MANAGER_ENABLED="${WEBHOOK_CERT_MANAGER_ENABLED:-0}"
WEBHOOK_TLS_SECRET_NAME="${WEBHOOK_TLS_SECRET_NAME:-}"
WEBHOOK_TLS_CA_BUNDLE="${WEBHOOK_TLS_CA_BUNDLE:-}"
INSTALL_CRDS="${INSTALL_CRDS:-1}"
SKIP_DEMO_CR="${SKIP_DEMO_CR:-0}"
SKIP_KIND_CREATE="${SKIP_KIND_CREATE:-0}"
CHART_NAME="x0tta-mesh-operator"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CHART_DIR="$REPO_ROOT/charts/x0tta-mesh-operator"
EXAMPLE_CR="$CHART_DIR/examples/meshcluster-production.yaml"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Parse args
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --cluster-name)   CLUSTER_NAME="$2"; shift 2 ;;
    --release-name)   HELM_RELEASE="$2"; shift 2 ;;
    --skip-build)     SKIP_BUILD=1; shift ;;
    --dao-gov-addr)   GOV_ADDRESS="$2"; shift 2 ;;
    --dao-tok-addr)   TOK_ADDRESS="$2"; shift 2 ;;
    *) warn "Unknown arg: $1"; shift ;;
  esac
done

OPERATOR_DEPLOYMENT="$HELM_RELEASE"
if [[ "$HELM_RELEASE" != *"$CHART_NAME"* ]]; then
  OPERATOR_DEPLOYMENT="${HELM_RELEASE}-${CHART_NAME}"
fi

EXISTING_RELEASE_NAMESPACE="$(helm list -A 2>/dev/null | awk -v rel="$HELM_RELEASE" 'NR>1 && $1==rel {print $2; exit}')"
if [[ -n "$EXISTING_RELEASE_NAMESPACE" && "$EXISTING_RELEASE_NAMESPACE" != "$K8S_NAMESPACE" ]]; then
  warn "  Helm release ${HELM_RELEASE} already exists in namespace ${EXISTING_RELEASE_NAMESPACE}; overriding K8S_NAMESPACE=${K8S_NAMESPACE} -> ${EXISTING_RELEASE_NAMESPACE}"
  K8S_NAMESPACE="$EXISTING_RELEASE_NAMESPACE"
fi

RELEASE_EXISTS="0"
if [[ -n "$EXISTING_RELEASE_NAMESPACE" ]]; then
  RELEASE_EXISTS="1"
fi

# ---------------------------------------------------------------------------
# Step 1 — Preflight checks
# ---------------------------------------------------------------------------
info "=== Step 1: Preflight checks ==="

for bin in kind kubectl helm docker; do
  if ! command -v "$bin" &>/dev/null; then
    error "$bin not found in PATH"
  fi
  info "  $bin: $(command -v "$bin")  $($bin version --short 2>/dev/null || $bin version 2>/dev/null | head -1)"
done

if ! docker info &>/dev/null; then
  error "Docker daemon not running"
fi

info "Preflight OK"

# ---------------------------------------------------------------------------
# Step 2 — Create kind cluster
# ---------------------------------------------------------------------------
info "=== Step 2: kind cluster '$CLUSTER_NAME' ==="

if [[ "$SKIP_KIND_CREATE" == "1" ]] || kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
  info "  Cluster '$CLUSTER_NAME' already exists — reusing"
else
  info "  Creating cluster (this takes ~60s)..."
  kind create cluster \
    --name "$CLUSTER_NAME" \
    --config - <<EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: ${CLUSTER_NAME}
nodes:
  - role: control-plane
    kubeadmConfigPatches:
      - |
        kind: InitConfiguration
        nodeRegistration:
          kubeletExtraArgs:
            node-labels: "ingress-ready=true"
    extraPortMappings:
      - containerPort: 30080
        hostPort: 8080
        protocol: TCP
      - containerPort: 30443
        hostPort: 8443
        protocol: TCP
  - role: worker
  - role: worker
EOF
  info "  Cluster created"
fi

# Point kubectl at the new cluster
kubectl config use-context "kind-${CLUSTER_NAME}" 2>/dev/null || true

# Wait for control-plane
info "  Waiting for nodes to be Ready..."
kubectl wait node --all --for=condition=Ready --timeout=120s

info "Cluster ready: $(kubectl get nodes --no-headers | awk '{print $1, $2}' | tr '\n' '  ')"

# ---------------------------------------------------------------------------
# Step 3 — Namespace
# ---------------------------------------------------------------------------
info "=== Step 3: Namespace '$K8S_NAMESPACE' ==="
kubectl create namespace "$K8S_NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
info "  Namespace OK"

# ---------------------------------------------------------------------------
# Step 4 — Helm install x0tta-mesh-operator
# ---------------------------------------------------------------------------
info "=== Step 4: Helm install x0tta-mesh-operator (release: ${HELM_RELEASE}) ==="

info "  Ensuring mesh-node image availability: ${MESH_NODE_IMAGE_REPO}:${MESH_NODE_IMAGE_TAG}"
IMAGE_REPO="$MESH_NODE_IMAGE_REPO" IMAGE_TAG="$MESH_NODE_IMAGE_TAG" KIND_CLUSTER="$CLUSTER_NAME" \
  "$REPO_ROOT/scripts/ops/ensure_mesh_node_image.sh"

info "  Ensuring image availability: ${IMAGE_REPO}:${IMAGE_TAG}"
IMAGE_REPO="$IMAGE_REPO" IMAGE_TAG="$IMAGE_TAG" KIND_CLUSTER="$CLUSTER_NAME" \
  "$REPO_ROOT/scripts/ops/ensure_mesh_operator_image.sh"

if [[ "$RELEASE_EXISTS" == "0" && "$INSTALL_CRDS" == "1" ]] && kubectl get customresourcedefinition meshclusters.x0tta6bl4.io >/dev/null 2>&1; then
  CRD_OWNER_RELEASE="$(kubectl get customresourcedefinition meshclusters.x0tta6bl4.io -o jsonpath='{.metadata.annotations.meta\\.helm\\.sh/release-name}' 2>/dev/null || true)"
  CRD_OWNER_NAMESPACE="$(kubectl get customresourcedefinition meshclusters.x0tta6bl4.io -o jsonpath='{.metadata.annotations.meta\\.helm\\.sh/release-namespace}' 2>/dev/null || true)"

  if [[ -n "$CRD_OWNER_RELEASE" && -n "$CRD_OWNER_NAMESPACE" ]]; then
    if [[ "$CRD_OWNER_RELEASE" != "$HELM_RELEASE" || "$CRD_OWNER_NAMESPACE" != "$K8S_NAMESPACE" ]]; then
      warn "  CRD meshclusters.x0tta6bl4.io is owned by ${CRD_OWNER_RELEASE}/${CRD_OWNER_NAMESPACE}; forcing installCRDs=0 to avoid Helm ownership conflicts"
      INSTALL_CRDS="0"
    fi
  else
    warn "  CRD meshclusters.x0tta6bl4.io exists without Helm ownership metadata; forcing installCRDs=0 to avoid import conflicts"
    INSTALL_CRDS="0"
  fi
fi

HELM_ARGS=(
  upgrade --install "$HELM_RELEASE" "$CHART_DIR"
  --namespace "$K8S_NAMESPACE"
  --create-namespace
  --set "operator.image.repository=${IMAGE_REPO}"
  --set "operator.image.tag=${IMAGE_TAG}"
  --set "operator.image.pullPolicy=IfNotPresent"
  --set "installCRDs=${INSTALL_CRDS}"
  --set "meshDefaults.pqc.enabled=true"
  --set "meshDefaults.pqc.kemAlgorithm=ML-KEM-768"
  --set "meshDefaults.pqc.dsaAlgorithm=ML-DSA-65"
  --set "meshDefaults.mapek.enabled=true"
  --set "meshDefaults.dao.enabled=true"
  --set "meshDefaults.dao.governance.onChain.enabled=true"
  --set "meshDefaults.dao.governance.onChain.chainId=84532"
  --set "meshDefaults.dao.governance.onChain.rpc=${BASE_SEPOLIA_RPC}"
  --wait
  --timeout 120s
)

if [[ "$ENABLE_WEBHOOKS" == "1" ]]; then
  HELM_ARGS+=(--set "operator.webhook.enabled=true")
  if [[ "$WEBHOOK_CERT_MANAGER_ENABLED" == "1" ]]; then
    HELM_ARGS+=(--set "operator.webhook.certManager.enabled=true")
  else
    if [[ -z "$WEBHOOK_TLS_SECRET_NAME" || -z "$WEBHOOK_TLS_CA_BUNDLE" ]]; then
      error "ENABLE_WEBHOOKS=1 without cert-manager requires WEBHOOK_TLS_SECRET_NAME and WEBHOOK_TLS_CA_BUNDLE"
    fi
    HELM_ARGS+=(--set "operator.webhook.certManager.enabled=false")
    HELM_ARGS+=(--set "operator.webhook.tls.secretName=${WEBHOOK_TLS_SECRET_NAME}")
    HELM_ARGS+=(--set "operator.webhook.tls.caBundle=${WEBHOOK_TLS_CA_BUNDLE}")
  fi
fi

# Inject DAO contract addresses if provided
if [[ -n "$GOV_ADDRESS" ]]; then
  HELM_ARGS+=(--set "meshDefaults.dao.governance.onChain.governanceAddress=${GOV_ADDRESS}")
fi
if [[ -n "$TOK_ADDRESS" ]]; then
  HELM_ARGS+=(--set "meshDefaults.dao.governance.onChain.tokenAddress=${TOK_ADDRESS}")
fi

info "  Running: helm ${HELM_ARGS[*]}"
helm "${HELM_ARGS[@]}"

info "  Helm release OK"

# ---------------------------------------------------------------------------
# Step 5 — Verify operator pod
# ---------------------------------------------------------------------------
info "=== Step 5: Operator pod health ==="

kubectl rollout status "deployment/${OPERATOR_DEPLOYMENT}" \
  -n "$K8S_NAMESPACE" --timeout=90s

OPERATOR_POD=$(kubectl get pod -n "$K8S_NAMESPACE" \
  -l app.kubernetes.io/name=x0tta-mesh-operator,app.kubernetes.io/instance=${HELM_RELEASE} \
  -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

if [[ -z "$OPERATOR_POD" ]]; then
  warn "  Operator pod not found (image may need to be built/pushed)"
else
  info "  Operator pod: $OPERATOR_POD"
  kubectl logs "$OPERATOR_POD" -n "$K8S_NAMESPACE" --tail=20 2>/dev/null || true
fi

# ---------------------------------------------------------------------------
# Step 6 — CRD registration check
# ---------------------------------------------------------------------------
info "=== Step 6: CRD verification ==="

if kubectl get crd meshclusters.x0tta6bl4.io &>/dev/null; then
  info "  CRD 'meshclusters.x0tta6bl4.io' registered OK"
else
  error "  CRD not found — check Helm installCRDs=true"
fi

# ---------------------------------------------------------------------------
# Step 7 — Apply demo MeshCluster CR
# ---------------------------------------------------------------------------
info "=== Step 7: Demo MeshCluster CR ==="

if [[ "$SKIP_DEMO_CR" == "1" ]]; then
  info "  SKIP_DEMO_CR=1 -> skipping demo MeshCluster apply"
else
  if [[ -f "$EXAMPLE_CR" ]]; then
    # Patch namespace to match our target
    sed "s/namespace: .*/namespace: ${K8S_NAMESPACE}/" "$EXAMPLE_CR" \
      | kubectl apply -n "$K8S_NAMESPACE" -f - 2>/dev/null \
      && info "  MeshCluster CR applied from $EXAMPLE_CR" \
      || warn "  Could not apply CR (operator image may not be running)"
  else
    warn "  Example CR not found at $EXAMPLE_CR, applying inline demo..."
    kubectl apply -n "$K8S_NAMESPACE" -f - <<EOF
apiVersion: x0tta6bl4.io/v1alpha1
kind: MeshCluster
metadata:
  name: dev-mesh
  namespace: ${K8S_NAMESPACE}
spec:
  replicas: 1
  trustDomain: x0tta6bl4.mesh
  pqc:
    enabled: true
    kemAlgorithm: ML-KEM-768
    dsaAlgorithm: ML-DSA-65
    ebpf:
      enabled: false       # disable in kind (no eBPF kernel support)
      xdpMode: skb
  fallback:
    enabled: true
    circuit:
      enabled: true
  mapek:
    enabled: true
EOF
  fi
fi

# ---------------------------------------------------------------------------
# Step 8 — Summary
# ---------------------------------------------------------------------------
info "=== Step 8: Summary ==="

echo ""
echo "  ┌─────────────────────────────────────────────────────┐"
echo "  │  x0tta6bl4 dev cluster: kind-${CLUSTER_NAME}"
echo "  │  Namespace  : ${K8S_NAMESPACE}"
echo "  │  Operator   : ${HELM_RELEASE} (${OPERATOR_DEPLOYMENT}) v${IMAGE_TAG}"
echo "  │  CRD        : meshclusters.x0tta6bl4.io ✓"
echo "  │  DAO chain  : Base Sepolia (84532)"
echo "  │  RPC        : ${BASE_SEPOLIA_RPC}"
if [[ -n "$GOV_ADDRESS" ]]; then
echo "  │  Governance : ${GOV_ADDRESS}"
fi
echo "  └─────────────────────────────────────────────────────┘"
echo ""
echo "  Quick commands:"
echo "    kubectl get mc -n ${K8S_NAMESPACE}           # list MeshClusters"
echo "    kubectl describe mc dev-mesh -n ${K8S_NAMESPACE}"
echo "    kubectl logs -l app.kubernetes.io/name=x0tta-mesh-operator,app.kubernetes.io/instance=${HELM_RELEASE} -n ${K8S_NAMESPACE}"
echo "    helm status ${HELM_RELEASE} -n ${K8S_NAMESPACE}"
echo "    kind delete cluster --name ${CLUSTER_NAME}   # teardown"
echo ""

info "Bootstrap complete."
