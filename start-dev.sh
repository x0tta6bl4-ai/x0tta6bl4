#!/bin/bash
###############################################################################
# x0tta6bl4 Development Mode Launcher
# Запуск системы в режиме разработки с auto-reload
###############################################################################

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

echo "🚀 x0tta6bl4 MAPE-K Development Mode"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Проверяем виртуальное окружение
if [ ! -d ".venv" ]; then
    echo "📦 Создание виртуального окружения..."
    python3.12 -m venv .venv
fi

source .venv/bin/activate

# Установка зависимостей
echo "📚 Установка зависимостей..."
pip install -e . -q 2>/dev/null || pip install -e .

# Создание .env файла если не существует
if [ ! -f ".env.development" ]; then
    echo "⚙️  Создание конфигурации .env.development..."
    cat > .env.development << 'EOF'
# Development Configuration
LOG_LEVEL=DEBUG
ENVIRONMENT=development
VERSION=3.1.0

# Prometheus
PROMETHEUS_URL=http://localhost:9090

# Charter
CHARTER_URL=http://localhost:8000
CHARTER_API_KEY=dev-key-12345

# Performance
WORKER_THREADS=2
CACHE_SIZE_MB=256
BATCH_SIZE=10

# Security
ENABLE_MTLS=false
TLS_CERT_PATH=./certs/server.crt
TLS_KEY_PATH=./certs/server.key
EOF
    echo "✅ Файл создан: .env.development"
fi

# Запуск в режиме разработки
echo ""
echo "✅ Запуск приложения в режиме разработки..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📍 API: http://localhost:8000"
echo "📊 Metrics: http://localhost:9090"
echo ""
echo "Команды:"
echo "  • Logs: tail -f mape-k.log"
echo "  • Tests: pytest tests/ -v"
echo "  • Health check: curl http://localhost:8000/health"
echo ""
echo "Нажмите Ctrl+C для остановки"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Запуск с auto-reload
exec python -m uvicorn src.core.app:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload \
    --reload-dirs src \
    --log-level debug
