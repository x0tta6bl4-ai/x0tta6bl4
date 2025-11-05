#!/bin/bash

# Скрипт настройки CI/CD pipeline для проекта x0tta6bl4
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
GITHUB_REPO="x0tta6bl4"
DOCKER_REGISTRY="your-registry.com"
NAMESPACE="development"
KUBECONFIG_SECRET="dev-kubeconfig"

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

    # Проверка Git
    if ! command -v git &> /dev/null; then
        log_error "Git не установлен."
        exit 1
    fi

    # Проверка Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker не установлен."
        exit 1
    fi

    # Проверка kubectl
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl не установлен."
        exit 1
    fi

    log_success "Все зависимости проверены"
}

# Создание директории для CI/CD
create_cicd_structure() {
    log_info "Создание структуры CI/CD..."

    mkdir -p .github/workflows
    mkdir -p .github/actions/{docker-build,deploy-k8s,test}
    mkdir -p ci-cd/{scripts,configs,templates}

    log_success "Структура создана"
}

# Создание GitHub Actions workflow для CI
create_ci_workflow() {
    log_info "Создание CI workflow..."

    cat > .github/workflows/ci.yml << 'EOF'
name: CI Pipeline

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

env:
  REGISTRY: ${{ secrets.DOCKER_REGISTRY }}
  IMAGE_NAME: x0tta6bl4

jobs:
  test:
    name: Run Tests
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.9, 3.10, 3.11]

    steps:
    - name: Checkout code
      uses: actions/checkout@v4

    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements-dev.txt
        pip install -r requirements.txt

    - name: Run linting
      run: |
        flake8 --config=.flake8 x0tta6bl4/ || true
        black --check x0tta6bl4/ || true

    - name: Run tests
      run: |
        pytest --cov=x0tta6bl4 --cov-report=xml --cov-report=term-missing tests/

    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        flags: unittests
        name: codecov-umbrella

  security-scan:
    name: Security Scan
    runs-on: ubuntu-latest
    needs: test

    steps:
    - name: Checkout code
      uses: actions/checkout@v4

    - name: Run Trivy vulnerability scanner
      uses: aquasecurity/trivy-action@master
      with:
        scan-type: 'fs'
        scan-ref: '.'
        format: 'sarif'
        output: 'trivy-results.sarif'

    - name: Upload Trivy scan results
      uses: github/codeql-action/upload-sarif@v2
      if: always()
      with:
        sarif_file: 'trivy-results.sarif'

  build-and-push:
    name: Build and Push Docker Image
    runs-on: ubuntu-latest
    needs: [test, security-scan]
    if: github.event_name == 'push'

    steps:
    - name: Checkout code
      uses: actions/checkout@v4

    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v3

    - name: Log in to Docker Registry
      uses: docker/login-action@v3
      with:
        registry: ${{ secrets.DOCKER_REGISTRY }}
        username: ${{ secrets.DOCKER_USERNAME }}
        password: ${{ secrets.DOCKER_PASSWORD }}

    - name: Extract metadata
      id: meta
      uses: docker/metadata-action@v5
      with:
        images: ${{ secrets.DOCKER_REGISTRY }}/${{ env.IMAGE_NAME }}
        tags: |
          type=ref,event=branch
          type=ref,event=pr
          type=sha,prefix={{branch}}-
          type=raw,value=latest,enable={{is_default_branch}}

    - name: Build and push Docker image
      uses: docker/build-push-action@v5
      with:
        context: .
        push: true
        tags: ${{ steps.meta.outputs.tags }}
        labels: ${{ steps.meta.outputs.labels }}
        cache-from: type=gha
        cache-to: type=gha,mode=max

    - name: Generate deployment package
      run: |
        mkdir -p deployment-package
        cp -r k8s-manifests/ deployment-package/
        cp -r ci-cd/ deployment-package/
        tar -czf deployment-${{ github.sha }}.tar.gz deployment-package/

    - name: Upload deployment package
      uses: actions/upload-artifact@v3
      with:
        name: deployment-package-${{ github.sha }}
        path: deployment-${{ github.sha }}.tar.gz
EOF

    log_success "CI workflow создан"
}

# Создание CD workflow для развертывания
create_cd_workflow() {
    log_info "Создание CD workflow..."

    cat > .github/workflows/cd.yml << 'EOF'
name: CD Pipeline

on:
  workflow_run:
    workflows: ["CI Pipeline"]
    types:
      - completed
  workflow_dispatch:
    inputs:
      environment:
        description: 'Environment to deploy to'
        required: true
        default: 'development'
        type: choice
        options:
        - development
        - staging
        - production

env:
  REGISTRY: ${{ secrets.DOCKER_REGISTRY }}
  IMAGE_NAME: x0tta6bl4
  K8S_NAMESPACE: ${{ github.event.inputs.environment || 'development' }}

jobs:
  deploy:
    name: Deploy to Kubernetes
    runs-on: ubuntu-latest
    if: ${{ github.event.workflow_run.conclusion == 'success' || github.event_name == 'workflow_dispatch' }}
    environment: ${{ github.event.inputs.environment || 'development' }}

    steps:
    - name: Checkout code
      uses: actions/checkout@v4

    - name: Download deployment package
      uses: actions/download-artifact@v3
      with:
        name: deployment-package-${{ github.sha }}
        path: .

    - name: Extract deployment package
      run: |
        tar -xzf deployment-*.tar.gz
        rm deployment-*.tar.gz

    - name: Set up kubectl
      uses: azure/k8s-set-context@v3
      with:
        method: kubeconfig
        kubeconfig: ${{ secrets.K8S_KUBECONFIG }}

    - name: Deploy to Kubernetes
      run: |
        cd deployment-package
        chmod +x ci-cd/scripts/deploy.sh
        ./ci-cd/scripts/deploy.sh ${{ env.K8S_NAMESPACE }}

    - name: Verify deployment
      run: |
        kubectl rollout status deployment/x0tta6bl4 -n ${{ env.K8S_NAMESPACE }} --timeout=300s
        kubectl get pods -n ${{ env.K8S_NAMESPACE }}
        kubectl get services -n ${{ env.K8S_NAMESPACE }}

    - name: Run integration tests
      run: |
        chmod +x ci-cd/scripts/integration-tests.sh
        ./ci-cd/scripts/integration-tests.sh ${{ env.K8S_NAMESPACE }}

  notify:
    name: Notify deployment status
    runs-on: ubuntu-latest
    needs: deploy
    if: always()

    steps:
    - name: Notify success
      if: needs.deploy.result == 'success'
      run: |
        echo "🚀 Deployment to ${{ env.K8S_NAMESPACE }} completed successfully!"

    - name: Notify failure
      if: needs.deploy.result == 'failure'
      run: |
        echo "❌ Deployment to ${{ env.K8S_NAMESPACE }} failed!"
        exit 1
EOF

    log_success "CD workflow создан"
}

# Создание скрипта развертывания
create_deploy_script() {
    log_info "Создание скрипта развертывания..."

    cat > ci-cd/scripts/deploy.sh << 'EOF'
#!/bin/bash
set -euo pipefail

NAMESPACE="${1:-development}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🚀 Starting deployment to namespace: $NAMESPACE"

# Проверка namespace
kubectl get namespace "$NAMESPACE" || kubectl create namespace "$NAMESPACE"

# Развертывание базовых ресурсов
echo "📦 Deploying base resources..."
kubectl apply -f k8s-manifests/base/ -n "$NAMESPACE"

# Развертывание сетевых политик
echo "🔒 Deploying network policies..."
kubectl apply -f k8s-manifests/networking/ -n "$NAMESPACE"

# Развертывание хранилища
echo "💾 Deploying storage..."
kubectl apply -f k8s-manifests/storage/ -n "$NAMESPACE"

# Развертывание мониторинга
echo "📊 Deploying monitoring..."
kubectl apply -f k8s-manifests/monitoring/ -n "$NAMESPACE"

# Развертывание приложения
echo "⚡ Deploying application..."
kubectl apply -f k8s-manifests/application/ -n "$NAMESPACE"

# Обновление изображений
echo "🔄 Updating container images..."
kubectl set image deployment/x0tta6bl4 "x0tta6bl4=*@${DOCKER_IMAGE_DIGEST}" -n "$NAMESPACE"

echo "✅ Deployment completed successfully!"
EOF

    chmod +x ci-cd/scripts/deploy.sh
    log_success "Скрипт развертывания создан"
}

# Создание скрипта интеграционных тестов
create_integration_test_script() {
    log_info "Создание скрипта интеграционных тестов..."

    cat > ci-cd/scripts/integration-tests.sh << 'EOF'
#!/bin/bash
set -euo pipefail

NAMESPACE="${1:-development}"
BASE_URL="http://x0tta6bl4.$NAMESPACE.svc.cluster.local"

echo "🧪 Running integration tests for namespace: $NAMESPACE"

# Ожидание готовности сервиса
echo "⏳ Waiting for service to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/x0tta6bl4 -n "$NAMESPACE"

# Проверка здоровья сервиса
echo "🏥 Checking service health..."
SERVICE_IP=$(kubectl get svc x0tta6bl4 -n "$NAMESPACE" -o jsonpath='{.spec.clusterIP}')
if [ -n "$SERVICE_IP" ] && [ "$SERVICE_IP" != "None" ]; then
    echo "✅ Service is accessible at: $SERVICE_IP"
else
    echo "❌ Service IP not found"
    exit 1
fi

# Проверка доступности портов
echo "🔌 Checking port accessibility..."
kubectl port-forward svc/x0tta6bl4 8080:80 -n "$NAMESPACE" &
PF_PID=$!

sleep 5

# Тестирование HTTP endpoint
if curl -f http://localhost:8080/health &>/dev/null; then
    echo "✅ Health check passed"
else
    echo "❌ Health check failed"
    kill $PF_PID
    exit 1
fi

kill $PF_PID

# Проверка метрик Prometheus
echo "📊 Checking Prometheus metrics..."
METRICS_PORT=$(kubectl get svc prometheus-kube-prometheus-prometheus -n monitoring -o jsonpath='{.spec.ports[?(@.name=="http-web")].port}' 2>/dev/null || echo "9090")

if [ -n "$METRICS_PORT" ]; then
    kubectl port-forward svc/prometheus-kube-prometheus-prometheus "$METRICS_PORT:9090" -n monitoring &
    PF_PID=$!

    sleep 5

    if curl -f "http://localhost:$METRICS_PORT/-/healthy" &>/dev/null; then
        echo "✅ Prometheus is healthy"
    else
        echo "❌ Prometheus health check failed"
    fi

    kill $PF_PID
fi

echo "🎉 All integration tests passed!"
EOF

    chmod +x ci-cd/scripts/integration-tests.sh
    log_success "Скрипт интеграционных тестов создан"
}

# Создание конфигурации для линтинга
create_linting_config() {
    log_info "Создание конфигурации линтинга..."

    cat > .flake8 << 'EOF'
[flake8]
max-line-length = 88
extend-ignore = E203, E266, E501, W503, F403, F401
max-complexity = 18
select = B,C,E,F,W,T4,B9
exclude =
    .git,
    __pycache__,
    .pytest_cache,
    .tox,
    venv,
    .venv,
    env,
    .env,
    node_modules,
    build,
    dist,
    *.egg-info
EOF

    cat > .pre-commit-config.yaml << 'EOF'
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files

  - repo: https://github.com/psf/black
    rev: 23.11.0
    hooks:
      - id: black
        language_version: python3.11

  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort
        args: ["--profile", "black"]

  - repo: https://github.com/pycqa/flake8
    rev: 6.1.0
    hooks:
      - id: flake8
EOF

    log_success "Конфигурация линтинга создана"
}

# Создание Dockerfile для приложения
create_dockerfile() {
    log_info "Создание Dockerfile..."

    cat > Dockerfile << 'EOF'
FROM python:3.11-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Создание непривилегированного пользователя
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Установка рабочей директории
WORKDIR /app

# Копирование и установка зависимостей
COPY requirements*.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода
COPY . .

# Создание директории для логов
RUN mkdir -p /app/logs && chown -R appuser:appuser /app

# Переключение на непривилегированного пользователя
USER appuser

# Экспорт порта
EXPOSE 8080

# Команда запуска
CMD ["uvicorn", "x0tta6bl4.main:app", "--host", "0.0.0.0", "--port", "8080", "--access-log"]
EOF

    log_success "Dockerfile создан"
}

# Создание docker-compose для локальной разработки
create_docker_compose() {
    log_info "Создание docker-compose.yml..."

    cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8080:8080"
    environment:
      - ENVIRONMENT=development
      - LOG_LEVEL=DEBUG
    volumes:
      - ./x0tta6bl4:/app/x0tta6bl4
      - ./logs:/app/logs
    depends_on:
      - postgres
      - redis
    networks:
      - x0tta6bl4-network

  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: x0tta6bl4
      POSTGRES_USER: x0tta6bl4
      POSTGRES_PASSWORD: dev_password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - x0tta6bl4-network

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    networks:
      - x0tta6bl4-network

  minio:
    image: minio/minio:latest
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: x0tta6bl4
      MINIO_ROOT_PASSWORD: dev_password
    volumes:
      - minio_data:/data
    networks:
      - x0tta6bl4-network
    command: server /data --console-address ":9001"

volumes:
  postgres_data:
  redis_data:
  minio_data:

networks:
  x0tta6bl4-network:
    driver: bridge
EOF

    log_success "docker-compose.yml создан"
}

# Создание Makefile для удобства разработки
create_makefile() {
    log_info "Создание Makefile..."

    cat > Makefile << 'EOF'
.PHONY: help install test lint format build up down logs clean

PYTHON := python3
PIP := $(PYTHON) -m pip

help: ## Показать эту справку
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Установить зависимости разработки
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements-dev.txt
	$(PIP) install -r requirements.txt

test: ## Запустить тесты
	$(PYTHON) -m pytest tests/ -v --cov=x0tta6bl4 --cov-report=term-missing --cov-report=html

test-watch: ## Запустить тесты в режиме наблюдения
	$(PYTHON) -m pytest tests/ -v --watch

lint: ## Запустить линтеры
	flake8 x0tta6bl4/
	black --check x0tta6bl4/
	isort --check-only x0tta6bl4/

format: ## Отформатировать код
	black x0tta6bl4/
	isort x0tta6bl4/

type-check: ## Проверить типы
	mypy x0tta6bl4/ --ignore-missing-imports

build: ## Собрать Docker образ
	docker build -t x0tta6bl4:latest .

up: ## Запустить сервисы локальной разработки
	docker-compose up -d

down: ## Остановить сервисы локальной разработки
	docker-compose down

logs: ## Показать логи сервисов
	docker-compose logs -f app

shell: ## Запустить shell в контейнере приложения
	docker-compose exec app bash

migrate: ## Выполнить миграции базы данных
	docker-compose exec app alembic upgrade head

clean: ## Очистить временные файлы
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	docker system prune -f

security-scan: ## Запустить сканирование безопасности
	trivy fs .
	safety check

ci: ## Запустить полный CI pipeline локально
	$(MAKE) lint
	$(MAKE) type-check
	$(MAKE) test

deploy-dev: ## Развернуть в среду разработки
	./infrastructure/development/kubernetes/setup-dev-cluster.sh

deploy-staging: ## Развернуть в staging среду
	kubectl apply -f k8s-manifests/staging/ -n staging

deploy-prod: ## Развернуть в production среду
	kubectl apply -f k8s-manifests/production/ -n production
EOF

    log_success "Makefile создан"
}

# Основная функция
main() {
    log_info "Настройка CI/CD pipeline для проекта x0tta6bl4"
    echo "=============================================="

    check_dependencies
    create_cicd_structure
    create_ci_workflow
    create_cd_workflow
    create_deploy_script
    create_integration_test_script
    create_linting_config
    create_dockerfile
    create_docker_compose
    create_makefile

    log_success "Настройка CI/CD завершена успешно!"
    echo
    log_info "Следующие шаги:"
    echo "1. Настройте секреты в GitHub repository:"
    echo "   - DOCKER_REGISTRY"
    echo "   - DOCKER_USERNAME"
    echo "   - DOCKER_PASSWORD"
    echo "   - K8S_KUBECONFIG"
    echo
    echo "2. Установите зависимости разработки:"
    echo "   make install"
    echo
    echo "3. Запустите локальную разработку:"
    echo "   make up"
    echo
    echo "4. Запустите тесты:"
    echo "   make test"
}

# Запуск основной функции
main "$@"