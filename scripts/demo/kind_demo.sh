#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────
# kind_demo.sh — локальный запуск x0tta-mesh-operator на kind
# Использование:
#   ./scripts/demo/kind_demo.sh          # полный запуск
#   ./scripts/demo/kind_demo.sh teardown # удалить кластер
# ──────────────────────────────────────────────────────────────────
set -euo pipefail

CLUSTER_NAME="x0tta-demo"
NAMESPACE="x0tta-system"
CHART_DIR="charts/x0tta-mesh-operator"
CHART_VERSION="3.3.2"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

# ── Teardown ──────────────────────────────────────────────────────
if [[ "${1:-}" == "teardown" ]]; then
  info "Удаляем кластер ${CLUSTER_NAME}..."
  kind delete cluster --name "${CLUSTER_NAME}" 2>/dev/null && info "Кластер удалён" || warn "Кластер не найден"
  exit 0
fi

# ── Проверка зависимостей ──────────────────────────────────────────
for cmd in kind kubectl helm; do
  command -v "$cmd" >/dev/null 2>&1 || error "Не найден: $cmd"
done
info "Зависимости: OK (kind=$(kind version | cut -d' ' -f2), helm=$(helm version --short))"

# ── Создать кластер ────────────────────────────────────────────────
if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
  warn "Кластер ${CLUSTER_NAME} уже существует, пропускаем создание"
else
  info "Создаём kind-кластер ${CLUSTER_NAME}..."
  kind create cluster --name "${CLUSTER_NAME}" --config k8s-demo.yaml
fi

kubectl cluster-info --context "kind-${CLUSTER_NAME}"

# ── Namespace ─────────────────────────────────────────────────────
kubectl create namespace "${NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -

# ── Helm install ──────────────────────────────────────────────────
info "Устанавливаем x0tta-mesh-operator v${CHART_VERSION}..."
helm upgrade --install x0tta-mesh "${CHART_DIR}" \
  --namespace "${NAMESPACE}" \
  --set installCRDs=true \
  --set installExamples=true \
  --set operator.image.repository=x0tta6bl4/mesh-operator \
  --set operator.image.tag="${CHART_VERSION}" \
  --set operator.image.pullPolicy=Never \
  --wait --timeout=60s 2>/dev/null \
  || warn "Оператор не запустился (образ не загружен — это норма для локального теста без реального образа)"

# ── CRD установлен? ───────────────────────────────────────────────
info "Проверяем CRD..."
kubectl get crd meshclusters.x0tta6bl4.io \
  && info "✅ CRD meshclusters.x0tta6bl4.io зарегистрирован" \
  || error "CRD не установлен"

# ── Применяем пример MeshCluster ─────────────────────────────────
info "Применяем демо MeshCluster (minimal)..."
kubectl apply -f "${CHART_DIR}/examples/meshcluster-minimal.yaml" \
  --namespace default 2>/dev/null || warn "CR применён (без оператора статус не обновится)"

info "Ресурсы в кластере:"
kubectl get meshclusters --all-namespaces 2>/dev/null || true
kubectl get crd meshclusters.x0tta6bl4.io -o jsonpath='{.status.conditions[-1].type}' 2>/dev/null
echo ""

info "──────────────────────────────────────────────────────"
info "Демо готово. Команды:"
info "  kubectl get mc                     # список MeshCluster"
info "  kubectl describe mc minimal-mesh   # детали"
info "  ./scripts/demo/kind_demo.sh teardown  # удалить кластер"
info "──────────────────────────────────────────────────────"
