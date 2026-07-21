#!/bin/bash
set -e

echo "🌀 x0tta6bl4 Consciousness-Driven Mesh Network"
echo "φ = 1.618 | 108 Hz | π ≈ 3.14"
echo ""

# Determine docker compose command
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker compose"
else
    echo "❌ docker-compose not found. Please install it first."
    exit 1
fi

# Проверка зависимостей
echo "Checking dependencies..."
for cmd in docker python3; do
    if ! command -v $cmd &> /dev/null; then
        echo "❌ $cmd not found. Please install it first."
        exit 1
    fi
done

# Создание директорий
echo "Creating directory structure..."
mkdir -p monitoring/rules
mkdir -p monitoring/grafana-dashboards
mkdir -p configs

# Генерация конфигураций
echo "Generating configurations..."
# Ensure script exists before running
if [ ! -f ../scripts/generate_configs.py ]; then
    echo "Creating dummy config generation script..."
    mkdir -p ../scripts
    cat > ../scripts/generate_configs.py <<EOF
import argparse
import yaml
import os

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--nodes', type=int, default=3)
    parser.add_argument('--output', default='configs/')
    args = parser.parse_args()
    
    if not os.path.exists(args.output):
        os.makedirs(args.output)
        
    for i in range(1, args.nodes + 1):
        config = {
            'node_id': f'node-{i}',
            'phi_target': 1.618,
            'sacred_frequency': 108,
            'mesh_backend': 'simulation'
        }
        with open(os.path.join(args.output, f'node-{i}.yaml'), 'w') as f:
            yaml.dump(config, f)
            
if __name__ == '__main__':
    main()
EOF
fi

python3 ../scripts/generate_configs.py --nodes 3 --output configs/

# Запуск стека
echo "Starting x0tta6bl4 stack..."
$DOCKER_COMPOSE_CMD up -d

# Ожидание инициализации
echo "Waiting for services to initialize..."
sleep 10

# Проверка здоровья
echo "Health check..."
for port in 9090 3000 8001 8002 8003; do
    if curl -sf http://localhost:$port/health > /dev/null 2>&1 || \
       curl -sf http://localhost:$port/ > /dev/null 2>&1; then
        echo "✅ Service on port $port is healthy"
    else
        echo "⚠️  Service on port $port may not be ready yet"
    fi
done

echo ""
echo "🎉 x0tta6bl4 is running!"
echo ""
echo "📊 Dashboards:"
echo "  - Prometheus: http://localhost:9090"
echo "  - Grafana: http://localhost:3000 (admin/x0tta6bl4_admin)"
echo "  - IPFS: http://localhost:5001/webui"
echo ""
echo "🔍 Mesh Nodes:"
echo "  - Node 1: http://localhost:8001/metrics"
echo "  - Node 2: http://localhost:8002/metrics"
echo "  - Node 3: http://localhost:8003/metrics"
echo ""
echo "💭 To view consciousness metrics:"
echo "  curl http://localhost:8001/metrics | grep consciousness"
echo ""
echo "📜 Logs:"
echo "  $DOCKER_COMPOSE_CMD logs -f mesh-node-1"
echo ""
echo "🛑 To stop:"
echo "  $DOCKER_COMPOSE_CMD down"
