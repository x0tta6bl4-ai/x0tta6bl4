#!/bin/bash

# Скрипт настройки Kubernetes кластера разработки для проекта x0tta6bl4
# Версия: 1.0.0
# Дата: Октябрь 2025

set -euo pipefail

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Конфигурация
CLUSTER_NAME="x0tta6bl4-dev"
NAMESPACE="development"
KUBECONFIG_DIR="$HOME/.kube"
KUBECONFIG_FILE="$KUBECONFIG_DIR/config"
HELM_VERSION="3.15.0"
MINIKUBE_VERSION="1.33.1"

# Функции логирования
log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

# Проверка зависимостей
check_dependencies() {
    log_info "Проверка зависимостей..."

    # Проверка Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker не установлен. Установите Docker и попробуйте снова."
        exit 1
    fi

    # Проверка kubectl
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl не установлен. Установите kubectl и попробуйте снова."
        exit 1
    fi

    # Проверка minikube
    if ! command -v minikube &> /dev/null; then
        log_warning "minikube не установлен. Устанавливаю..."
        install_minikube
    fi

    # Проверка helm
    if ! command -v helm &> /dev/null; then
        log_warning "Helm не установлен. Устанавливаю..."
        install_helm
    fi

    log_success "Все зависимости проверены"
}

# Установка minikube
install_minikube() {
    log_info "Установка minikube версии $MINIKUBE_VERSION..."

    curl -LO "https://storage.googleapis.com/minikube/releases/v${MINIKUBE_VERSION}/minikube-linux-amd64"
    sudo install minikube-linux-amd64 /usr/local/bin/minikube
    rm minikube-linux-amd64

    log_success "minikube установлен"
}

# Установка Helm
install_helm() {
    log_info "Установка Helm версии $HELM_VERSION..."

    curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3
    chmod 700 get_helm.sh
    ./get_helm.sh --version v$HELM_VERSION
    rm get_helm.sh

    log_success "Helm установлен"
}

# Создание директории для kubeconfig
create_kubeconfig_dir() {
    if [ ! -d "$KUBECONFIG_DIR" ]; then
        log_info "Создание директории для kubeconfig..."
        mkdir -p "$KUBECONFIG_DIR"
        log_success "Директория создана"
    fi
}

# Запуск minikube
start_minikube() {
    log_info "Запуск minikube кластера..."

    # Остановка существующего кластера если он запущен
    if minikube status --profile=$CLUSTER_NAME &>/dev/null; then
        log_info "Остановка существующего кластера..."
        minikube stop --profile=$CLUSTER_NAME
        minikube delete --profile=$CLUSTER_NAME
    fi

    # Запуск нового кластера
    minikube start \
        --profile=$CLUSTER_NAME \
        --cpus=4 \
        --memory=8192 \
        --disk-size=50g \
        --kubernetes-version=v1.28.0 \
        --driver=docker \
        --ports=80:80 \
        --ports=443:443 \
        --ports=30000-32767:30000-32767 \
        --embed-certs \
        --addons=ingress \
        --addons=ingress-dns \
        --addons=metrics-server

    # Настройка kubectl для работы с кластером
    minikube update-context --profile=$CLUSTER_NAME

    log_success "Кластер запущен"
}

# Настройка namespace разработки
setup_namespace() {
    log_info "Настройка namespace разработки..."

    # Создание namespace
    kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -

    # Создание service account для разработки
    kubectl apply -f - <<EOF
apiVersion: v1
kind: ServiceAccount
metadata:
  name: dev-service-account
  namespace: $NAMESPACE
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: $NAMESPACE
  name: dev-role
rules:
- apiGroups: ["", "apps", "networking.k8s.io", "batch"]
  resources: ["*"]
  verbs: ["*"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: dev-role-binding
  namespace: $NAMESPACE
subjects:
- kind: ServiceAccount
  name: dev-service-account
  namespace: $NAMESPACE
roleRef:
  kind: Role
  name: dev-role
  apiGroup: rbac.authorization.k8s.io
EOF

    log_success "Namespace настроен"
}

# Установка базовых инструментов мониторинга
install_monitoring() {
    log_info "Установка инструментов мониторинга..."

    # Добавление репозиториев Helm
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
    helm repo add grafana https://grafana.github.io/helm-charts
    helm repo update

    # Установка Prometheus
    helm install prometheus prometheus-community/kube-prometheus-stack \
        --namespace $NAMESPACE \
        --create-namespace \
        --set prometheus.service.type=NodePort \
        --set grafana.service.type=NodePort \
        --set prometheus-node-exporter.hostRootFsMount.enabled=false

    log_success "Мониторинг установлен"
}

# Настройка Ingress контроллера
setup_ingress() {
    log_info "Настройка Ingress контроллера..."

    # Установка nginx ingress controller
    helm install nginx-ingress ingress-nginx/ingress-nginx \
        --namespace $NAMESPACE \
        --set controller.replicaCount=2 \
        --set controller.nodeSelector."beta\.kubernetes\.io/os"=linux \
        --set defaultBackend.nodeSelector."beta\.kubernetes\.io/os"=linux \
        --set controller.admissionWebhooks.patch.nodeSelector."beta\.kubernetes\.io/os"=linux

    log_success "Ingress контроллер настроен"
}

# Создание тестового приложения
create_test_app() {
    log_info "Создание тестового приложения..."

    # Создание простого тестового приложения
    kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: test-app
  namespace: $NAMESPACE
spec:
  replicas: 2
  selector:
    matchLabels:
      app: test-app
  template:
    metadata:
      labels:
        app: test-app
    spec:
      containers:
      - name: test-app
        image: nginx:alpine
        ports:
        - containerPort: 80
        resources:
          requests:
            memory: "64Mi"
            cpu: "100m"
          limits:
            memory: "128Mi"
            cpu: "200m"
---
apiVersion: v1
kind: Service
metadata:
  name: test-app-service
  namespace: $NAMESPACE
spec:
  selector:
    app: test-app
  ports:
    - protocol: TCP
      port: 80
      targetPort: 80
  type: ClusterIP
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: test-app-ingress
  namespace: $NAMESPACE
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  ingressClassName: nginx
  rules:
  - host: test-app.local
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: test-app-service
            port:
              number: 80
EOF

    log_success "Тестовое приложение создано"
}

# Настройка локального DNS
setup_local_dns() {
    log_info "Настройка локального DNS..."

    # Добавление записи в /etc/hosts
    if ! grep -q "test-app.local" /etc/hosts; then
        echo "$(minikube ip) test-app.local" | sudo tee -a /etc/hosts
        log_success "DNS запись добавлена"
    else
        log_info "DNS запись уже существует"
    fi
}

# Вывод информации о кластере
show_cluster_info() {
    log_info "Информация о кластере:"
    echo
    echo "Cluster IP: $(minikube ip)"
    echo "Kubeconfig: $KUBECONFIG_FILE"
    echo "Namespace: $NAMESPACE"
    echo "Test App URL: http://test-app.local"
    echo
    echo "Команды для проверки:"
    echo "kubectl get pods -n $NAMESPACE"
    echo "kubectl get services -n $NAMESPACE"
    echo "kubectl get ingress -n $NAMESPACE"
    echo
    echo "Доступ к Grafana:"
    echo "kubectl port-forward -n $NAMESPACE svc/prometheus-grafana 3000:80"
    echo "URL: http://localhost:3000 (admin/prom-operator)"
    echo
    echo "Доступ к Prometheus:"
    echo "kubectl port-forward -n $NAMESPACE svc/prometheus-kube-prometheus-prometheus 9090:9090"
    echo "URL: http://localhost:9090"
}

# Основная функция
main() {
    log_info "Настройка Kubernetes кластера разработки для проекта x0tta6bl4"
    echo "================================================================="

    check_dependencies
    create_kubeconfig_dir
    start_minikube
    setup_namespace
    install_monitoring
    setup_ingress
    create_test_app
    setup_local_dns
    show_cluster_info

    log_success "Настройка кластера завершена успешно!"
    echo
    log_info "Кластер готов к разработке. Используйте 'minikube dashboard' для доступа к веб-интерфейсу."
}

# Запуск основной функции
main "$@"