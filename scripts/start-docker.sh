#!/bin/bash
###############################################################################
# x0tta6bl4 Docker Compose Launcher
# Полный стек с Prometheus, Charter, Redis, PostgreSQL
###############################################################################

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

echo "🐳 x0tta6bl4 Full Stack (Docker Compose)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Проверяем docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен. Установите Docker сначала."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose не установлен."
    exit 1
fi

# Создание .env файла если не существует
if [ ! -f ".env.docker" ]; then
    echo "⚙️  Создание конфигурации .env.docker..."
    cat > .env.docker << 'EOF'
# Docker Configuration
LOG_LEVEL=INFO
ENVIRONMENT=staging
VERSION=3.1.0

# Services
PROMETHEUS_URL=http://prometheus:9090
CHARTER_URL=http://charter:8000
REDIS_URL=redis://redis:6379
DATABASE_URL=postgresql://x0tta6:x0tta6@postgres:5432/x0tta6

# API
API_PORT=8000
METRICS_PORT=9090

# Performance
WORKER_THREADS=4
CACHE_SIZE_MB=512
BATCH_SIZE=50
EOF
    echo "✅ Файл создан: .env.docker"
fi

# Выбор режима
MODE=${1:-full}

case $MODE in
    full)
        echo "📦 Запуск ПОЛНОГО стека..."
        COMPOSE_FILE="docker-compose.yml"
        ;;
    minimal)
        echo "📦 Запуск МИНИМАЛЬНОГО стека..."
        COMPOSE_FILE="docker-compose.minimal.yml"
        ;;
    *)
        echo "❌ Неизвестный режим: $MODE"
        echo "Использование: ./start-docker.sh [full|minimal]"
        exit 1
        ;;
esac

# Проверяем наличие compose файла
if [ ! -f "$COMPOSE_FILE" ]; then
    echo "❌ Файл $COMPOSE_FILE не найден"
    exit 1
fi

# Остановка существующих контейнеров
echo ""
echo "🛑 Остановка существующих контейнеров..."
docker-compose -f "$COMPOSE_FILE" down 2>/dev/null || true

# Очистка old images
echo "🧹 Очистка неиспользуемых образов..."
docker system prune -f --volumes 2>/dev/null || true

# Запуск
echo ""
echo "🚀 Запуск стека..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

docker-compose -f "$COMPOSE_FILE" up --build

# На случай завершения
echo ""
echo "⚠️  Контейнеры остановлены."
echo "Для очистки: docker-compose -f $COMPOSE_FILE down"
