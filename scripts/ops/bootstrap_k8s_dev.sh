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
#   ./scripts/ops/bootstrap_k8s_dev.sh [--cluster-name NAME] [--skip-build]
#                                       [--dao-gov-addr 0x...] [--dao-tok-addr 0x...]
#
# Env overrides:
#   CLUSTER_NAME        kind cluster name         (default: x0tta-dev)
#   K8S_NAMESPACE       operator namespace         (default: x0tta-system)
#   IMAGE_TAG           mesh-operator image tag    (default: 3.4.0)
#   BASE_SEPOLIA_RPC    DAO RPC endpoint           (default: https://sepolia.base.org)
#   GOV_ADDRESS         MeshGovernance address     (default: "")
#   TOK_ADDRESS         X0TToken address           (default: "")
#   SKIP_KIND_CREATE    set to "1" to reuse existing cluster
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
CLUSTER_NAME="${CLUSTER_NAME:-x0tta-dev}"
K8S_NAMESPACE="${K8S_NAMESPACE:-x0tta-system}"
IMAGE_TAG="${IMAGE_TAG:-3.4.0}"
BASE_SEPOLIA_RPC="${BASE_SEPOLIA_RPC:-https://sepolia.base.org}"
GOV_ADDRESS="${GOV_ADDRESS:-}"
TOK_ADDRESS="${TOK_ADDRESS:-}"
SKIP_KIND_CREATE="${SKIP_KIND_CREATE:-0}"

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
    --skip-build)     SKIP_BUILD=1; shift ;;
    --dao-gov-addr)   GOV_ADDRESS="$2"; shift 2 ;;
    --dao-tok-addr)   TOK_ADDRESS="$2"; shift 2 ;;
    *) warn "Unknown arg: $1"; shift ;;
  esac
done

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
info "=== Step 4: Helm install x0tta-mesh-operator ==="

HELM_ARGS=(
  upgrade --install mesh-operator "$CHART_DIR"
  --namespace "$K8S_NAMESPACE"
  --create-namespace
  --set "operator.image.tag=${IMAGE_TAG}"
  --set "operator.image.pullPolicy=IfNotPresent"
  --set "installCRDs=true"
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

kubectl rollout status deployment/mesh-operator \
  -n "$K8S_NAMESPACE" --timeout=90s

OPERATOR_POD=$(kubectl get pod -n "$K8S_NAMESPACE" \
  -l app.kubernetes.io/name=x0tta-mesh-operator \
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

# ---------------------------------------------------------------------------
# Step 8 — Summary
# ---------------------------------------------------------------------------
info "=== Step 8: Summary ==="

echo ""
echo "  ┌─────────────────────────────────────────────────────┐"
echo "  │  x0tta6bl4 dev cluster: kind-${CLUSTER_NAME}"
echo "  │  Namespace  : ${K8S_NAMESPACE}"
echo "  │  Operator   : mesh-operator v${IMAGE_TAG}"
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
echo "    kubectl logs -l app.kubernetes.io/name=x0tta-mesh-operator -n ${K8S_NAMESPACE}"
echo "    helm list -n ${K8S_NAMESPACE}"
echo "    kind delete cluster --name ${CLUSTER_NAME}   # teardown"
echo ""

info "Bootstrap complete."
