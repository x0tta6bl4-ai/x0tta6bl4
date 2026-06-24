#!/bin/bash
set -e

echo "🧪 x0tta6bl4 Chaos Engineering Suite"
echo "======================================"
echo ""

# Убеждаемся, что система запущена
if ! docker ps | grep -q x0tta6bl4-node-1; then
    echo "❌ System is not running. Start it first with ./quickstart.sh"
    exit 1
fi

echo "✓ System is running"
echo ""

# Устанавливаем зависимости для chaos-тестов
echo "📦 Installing chaos dependencies..."
# Use pip with --break-system-packages as this is a dedicated environment
if ! python3 -c "import aiohttp" 2>/dev/null; then
    pip install pytest pytest-asyncio aiohttp --break-system-packages
fi

# Даем системе время "проснуться"
echo "⏳ Waiting for system warmup (30s)..."
sleep 30

# Базовая проверка здоровья
echo "🏥 Health check..."
for port in 8001 8002 8003; do
    if curl -sf http://localhost:$port/metrics | grep -q consciousness_phi_ratio; then
        echo "  ✓ Node on port $port is conscious"
    else
        echo "  ✗ Node on port $port is not responding"
    fi
done

echo ""
echo "🚀 Starting chaos tests..."
echo ""

# Запускаем тесты
cd ..
python3 -m pytest tests/chaos/test_consciousness_recovery.py -v -s

# Сохраняем результаты
mkdir -p deploy/test-results
docker logs x0tta6bl4-node-1 > deploy/test-results/node-1.log 2>&1
docker logs x0tta6bl4-node-2 > deploy/test-results/node-2.log 2>&1
docker logs x0tta6bl4-node-3 > deploy/test-results/node-3.log 2>&1

echo ""
echo "📜 Logs saved to deploy/test-results/"
echo ""
echo "✨ Chaos testing complete!"
