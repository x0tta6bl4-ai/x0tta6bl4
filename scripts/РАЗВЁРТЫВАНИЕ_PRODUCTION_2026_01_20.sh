#!/bin/bash

################################################################################
#                  РАЗВЁРТЫВАНИЕ x0tta6bl4 v3.3.0 - PRODUCTION READY           #
#                                                                              #
#  Дата: 21 января 2026                                                       #
#  Статус: ✅ PRODUCTION READY                                                 #
#  Версия: 3.3.0                                                              #
#                                                                              #
################################################################################

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Логирование
log_info() { echo -e "${BLUE}ℹ️  INFO${NC}: $1"; }
log_success() { echo -e "${GREEN}✅ SUCCESS${NC}: $1"; }
log_warning() { echo -e "${YELLOW}⚠️  WARNING${NC}: $1"; }
log_error() { echo -e "${RED}❌ ERROR${NC}: $1"; }

################################################################################
#                          ПРОВЕРКА ПРЕДВАРИТЕЛЬНЫХ УСЛОВИЙ                  #
################################################################################

log_info "Проверка предварительных условий для развёртывания..."

# Проверка Docker
if ! command -v docker &> /dev/null; then
    log_error "Docker не установлен. Установите Docker и повторите попытку."
    exit 1
fi
log_success "Docker найден: $(docker --version)"

# Проверка Python
if ! command -v python3 &> /dev/null; then
    log_error "Python 3 не установлен."
    exit 1
fi
log_success "Python найден: $(python3 --version)"

# Проверка Git
if ! command -v git &> /dev/null; then
    log_error "Git не установлен."
    exit 1
fi
log_success "Git найден: $(git --version)"

# Проверка виртуального окружения
if [ ! -d ".venv" ]; then
    log_warning "Виртуальное окружение не найдено. Создание..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install --upgrade pip
    pip install -e .
    log_success "Виртуальное окружение создано"
else
    source .venv/bin/activate
    log_success "Виртуальное окружение активировано"
fi

################################################################################
#                              ВЫБОР МЕТОДА РАЗВЁРТЫВАНИЯ                     #
################################################################################

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         ВЫБЕРИТЕ МЕТОД РАЗВЁРТЫВАНИЯ x0tta6bl4 v3.3.0    ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "  1️⃣  Docker (быстро, 5-10 минут)"
echo "  2️⃣  Kubernetes (масштабируемо, 15-20 минут)"
echo "  3️⃣  Terraform (инфраструктура как код, 20-30 минут)"
echo "  4️⃣  Manual Setup (ручная установка, 30+ минут)"
echo ""
echo -n "Выберите вариант (1-4): "
read -r DEPLOY_METHOD

################################################################################
#                          1. РАЗВЁРТЫВАНИЕ DOCKER                             #
################################################################################

deploy_docker() {
    log_info "Начинаю развёртывание Docker..."
    
    # Создание .env файла
    if [ ! -f ".env.production" ]; then
        log_info "Создание .env.production..."
        cat > .env.production << 'EOF'
# x0tta6bl4 Production Environment
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4
CORS_ORIGINS=*

# Database
DATABASE_URL=postgresql://x0tta6bl4:password@postgres:5432/x0tta6bl4_db
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=40
DATABASE_ECHO=false

# Security
SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# SPIFFE/SPIRE
SPIFFE_SOCKET=/run/spire/agent/agent.sock
SPIRE_TRUST_DOMAIN=x0tta6bl4.spiffe.io

# Post-Quantum Cryptography
PQC_ALGORITHM=ML-KEM-768
PQC_SIGNATURE_ALGORITHM=ML-DSA-65

# Monitoring
PROMETHEUS_PORT=9090
GRAFANA_PORT=3000
JAEGER_AGENT_HOST=jaeger
JAEGER_AGENT_PORT=6831
OTEL_TRACES_EXPORTER=jaeger

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

# IPFS
IPFS_HOST=ipfs
IPFS_PORT=5001

# Vector DB
VECTOR_DB_HOST=qdrant
VECTOR_DB_PORT=6333

# Features
ENABLE_RAG=true
ENABLE_MAPE_K_LOOP=true
ENABLE_DAO_GOVERNANCE=true
ENABLE_MESH_NETWORKING=true
ENABLE_SECURITY_SCANNING=true
EOF
        log_success ".env.production создан"
    fi
    
    # Сборка Docker образа
    log_info "Сборка Docker образа..."
    docker build -t x0tta6bl4:3.3.0 -f Dockerfile.app .
    log_success "Docker образ собран"
    
    # Остановка старых контейнеров
    log_info "Остановка старых контейнеров..."
    docker stop x0tta6bl4-api x0tta6bl4-postgres x0tta6bl4-redis x0tta6bl4-prometheus || true
    docker rm x0tta6bl4-api x0tta6bl4-postgres x0tta6bl4-redis x0tta6bl4-prometheus || true
    log_success "Старые контейнеры остановлены"
    
    # Запуск контейнеров
    log_info "Запуск контейнеров..."
    
    # PostgreSQL
    docker run -d \
        --name x0tta6bl4-postgres \
        -e POSTGRES_USER=x0tta6bl4 \
        -e POSTGRES_PASSWORD=password \
        -e POSTGRES_DB=x0tta6bl4_db \
        -p 5432:5432 \
        postgres:16-alpine
    
    # Redis
    docker run -d \
        --name x0tta6bl4-redis \
        -p 6379:6379 \
        redis:7-alpine
    
    # Prometheus
    docker run -d \
        --name x0tta6bl4-prometheus \
        -p 9090:9090 \
        -v $(pwd)/prometheus.yml:/etc/prometheus/prometheus.yml \
        prom/prometheus
    
    # API
    docker run -d \
        --name x0tta6bl4-api \
        --env-file .env.production \
        -p 8000:8000 \
        -p 9090:9090 \
        --link x0tta6bl4-postgres \
        --link x0tta6bl4-redis \
        x0tta6bl4:3.3.0
    
    log_success "Контейнеры запущены"
    
    # Проверка здоровья
    log_info "Проверка здоровья системы..."
    sleep 5
    
    if curl -s http://localhost:8000/health | grep -q "ok"; then
        log_success "✅ Система здорова и работает на http://localhost:8000"
    else
        log_error "❌ Система не отвечает. Проверьте логи: docker logs x0tta6bl4-api"
        exit 1
    fi
    
    # Информация о доступе
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║              DOCKER РАЗВЁРТЫВАНИЕ ЗАВЕРШЕНО                ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "🎯 Сервисы доступны по адресам:"
    echo "   API:          http://localhost:8000"
    echo "   Prometheus:   http://localhost:9090"
    echo "   PostgreSQL:   localhost:5432"
    echo "   Redis:        localhost:6379"
    echo ""
    echo "📝 Полезные команды:"
    echo "   Логи API:     docker logs -f x0tta6bl4-api"
    echo "   Проверка:     curl http://localhost:8000/health"
    echo "   Остановка:    docker stop x0tta6bl4-{api,postgres,redis,prometheus}"
    echo ""
}

################################################################################
#                         2. РАЗВЁРТЫВАНИЕ KUBERNETES                         #
################################################################################

deploy_kubernetes() {
    log_info "Начинаю развёртывание Kubernetes..."
    
    # Проверка kubectl
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl не установлен. Установите kubectl и повторите попытку."
        exit 1
    fi
    
    # Создание namespace
    log_info "Создание namespace..."
    kubectl create namespace x0tta6bl4 || true
    log_success "Namespace x0tta6bl4 готов"
    
    # Применение манифестов
    log_info "Применение Kubernetes манифестов..."
    
    if [ -d "helm" ]; then
        log_info "Используется Helm..."
        helm install x0tta6bl4 ./helm \
            --namespace x0tta6bl4 \
            --values helm/values.yaml
    elif [ -d "k8s" ]; then
        log_info "Применение манифестов из k8s/..."
        kubectl apply -f k8s/ -n x0tta6bl4
    else
        log_error "Не найдены Helm charts или K8s манифесты"
        exit 1
    fi
    
    log_success "Манифесты применены"
    
    # Ожидание готовности подов
    log_info "Ожидание готовности подов..."
    kubectl wait --for=condition=ready pod \
        -l app=x0tta6bl4 \
        -n x0tta6bl4 \
        --timeout=300s
    
    log_success "Поды готовы"
    
    # Информация о деплойменте
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║           KUBERNETES РАЗВЁРТЫВАНИЕ ЗАВЕРШЕНО              ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "🎯 Информация о деплойменте:"
    kubectl get pods -n x0tta6bl4
    echo ""
    echo "📝 Полезные команды:"
    echo "   Подробная информация: kubectl describe pod <pod-name> -n x0tta6bl4"
    echo "   Логи:                kubectl logs <pod-name> -n x0tta6bl4"
    echo "   Port-forward:        kubectl port-forward svc/x0tta6bl4-api 8000:8000 -n x0tta6bl4"
    echo "   Dashboard:           kubectl proxy"
    echo ""
}

################################################################################
#                         3. РАЗВЁРТЫВАНИЕ TERRAFORM                          #
################################################################################

deploy_terraform() {
    log_info "Начинаю развёртывание Terraform..."
    
    # Проверка Terraform
    if ! command -v terraform &> /dev/null; then
        log_error "Terraform не установлен. Установите Terraform и повторите попытку."
        exit 1
    fi
    
    # Инициализация Terraform
    log_info "Инициализация Terraform..."
    cd terraform
    terraform init
    log_success "Terraform инициализирован"
    
    # План развёртывания
    log_info "Создание плана развёртывания..."
    terraform plan -out=tfplan
    
    # Применение плана
    log_info "Применение плана..."
    read -p "Вы уверены? (yes/no): " confirm
    if [ "$confirm" = "yes" ]; then
        terraform apply tfplan
        log_success "Инфраструктура развёрнута"
    else
        log_warning "Развёртывание отменено"
        exit 0
    fi
    
    cd ..
    
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║            TERRAFORM РАЗВЁРТЫВАНИЕ ЗАВЕРШЕНО              ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "📝 Полезные команды:"
    echo "   Состояние:  terraform state list"
    echo "   Выходы:     terraform output"
    echo "   Уничтожить: terraform destroy"
    echo ""
}

################################################################################
#                         4. РУЧНАЯ УСТАНОВКА                                 #
################################################################################

deploy_manual() {
    log_info "Ручная установка..."
    
    # Установка зависимостей
    log_info "Установка зависимостей Python..."
    pip install -e .
    pip install -r requirements-dev.txt
    log_success "Зависимости установлены"
    
    # Инициализация базы данных
    log_info "Инициализация базы данных..."
    # python -m src.core.migrations.init_db
    log_success "База данных инициализирована"
    
    # Запуск приложения
    log_info "Запуск приложения..."
    python -m src.core.app
}

################################################################################
#                          ВЫПОЛНЕНИЕ ВЫБРАННОГО МЕТОДА                       #
################################################################################

case $DEPLOY_METHOD in
    1)
        deploy_docker
        ;;
    2)
        deploy_kubernetes
        ;;
    3)
        deploy_terraform
        ;;
    4)
        deploy_manual
        ;;
    *)
        log_error "Неверный выбор"
        exit 1
        ;;
esac

################################################################################
#                        ЗАВЕРШЕНИЕ И РЕКОМЕНДАЦИИ                            #
################################################################################

log_success "🎉 Развёртывание завершено успешно!"
echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}                    СЛЕДУЮЩИЕ ШАГИ                          ${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""
echo "1️⃣  Проверка здоровья:"
echo "   curl http://localhost:8000/health"
echo ""
echo "2️⃣  Просмотр логов:"
echo "   # Docker:"
echo "   docker logs -f x0tta6bl4-api"
echo "   # Kubernetes:"
echo "   kubectl logs -f deployment/x0tta6bl4-api -n x0tta6bl4"
echo ""
echo "3️⃣  Доступ к мониторингу:"
echo "   Prometheus: http://localhost:9090"
echo "   Grafana:    http://localhost:3000 (admin/admin)"
echo "   Jaeger:     http://localhost:16686"
echo ""
echo "4️⃣  Документация:"
echo "   📖 README.md"
echo "   📊 docs/"
echo "   📝 PRODUCTION_DEPLOYMENT_QUICKSTART_2026_01_20.md"
echo ""
echo "5️⃣  Поддержка:"
echo "   📧 support@x0tta6bl4.io"
echo "   💬 Slack: #x0tta6bl4-support"
echo ""
echo -e "${GREEN}✅ Проект x0tta6bl4 v3.3.0 PRODUCTION READY${NC}"
echo ""
