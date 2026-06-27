#!/bin/bash
# Скрипт для тестирования mesh сети в Docker
# Использование: ./scripts/mesh-test.sh [command]

set -e

COMPOSE_FILE="docker/docker-compose.mesh.yml"
PROJECT_NAME="x0tta6bl4-mesh"

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}======================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}======================================${NC}"
}

cmd_build() {
    print_header "Building Mesh Nodes"
    docker compose -f $COMPOSE_FILE -p $PROJECT_NAME build
    echo -e "${GREEN}✓ Build complete${NC}"
}

cmd_up() {
    print_header "Starting Mesh Network"
    docker compose -f $COMPOSE_FILE -p $PROJECT_NAME up -d
    echo -e "${GREEN}✓ Mesh network started${NC}"
    echo ""
    echo "Nodes:"
    echo "  - node-alpha: localhost:5001"
    echo "  - node-beta:  localhost:5002"
    echo "  - node-gamma: localhost:5003"
    echo "  - node-delta: localhost:5004"
    echo ""
    echo "Monitoring:"
    echo "  - Prometheus: http://localhost:9090"
    echo "  - Grafana:    http://localhost:3000 (admin/admin)"
}

cmd_down() {
    print_header "Stopping Mesh Network"
    docker compose -f $COMPOSE_FILE -p $PROJECT_NAME down
    echo -e "${GREEN}✓ Mesh network stopped${NC}"
}

cmd_logs() {
    docker compose -f $COMPOSE_FILE -p $PROJECT_NAME logs -f ${2:-}
}

cmd_status() {
    print_header "Mesh Network Status"
    docker compose -f $COMPOSE_FILE -p $PROJECT_NAME ps
    echo ""
    
    echo -e "${YELLOW}Node Discovery Status:${NC}"
    for node in alpha beta gamma delta; do
        container="mesh-node-$node"
        if docker ps --format '{{.Names}}' | grep -q $container; then
            peers=$(docker logs $container 2>&1 | grep -c "Пир найден" || echo "0")
            echo -e "  $container: ${GREEN}running${NC}, peers discovered: $peers"
        else
            echo -e "  $container: ${RED}stopped${NC}"
        fi
    done
}

cmd_test() {
    print_header "Running Mesh Tests"
    
    # Ждём запуска
    echo "Waiting for nodes to start..."
    sleep 5
    
    # Проверяем что все узлы запущены
    for node in alpha beta gamma delta; do
        container="mesh-node-$node"
        if ! docker ps --format '{{.Names}}' | grep -q $container; then
            echo -e "${RED}ERROR: $container is not running${NC}"
            exit 1
        fi
    done
    
    echo -e "${GREEN}✓ All nodes running${NC}"
    
    # Проверяем discovery
    echo ""
    echo "Checking peer discovery..."
    sleep 10
    
    total_peers=0
    for node in alpha beta gamma delta; do
        container="mesh-node-$node"
        peers=$(docker logs $container 2>&1 | grep -c "Пир найден" || echo "0")
        echo "  $container: $peers peers discovered"
        total_peers=$((total_peers + peers))
    done
    
    # В идеале каждый узел видит 3 других = 12 total discoveries
    if [ $total_peers -ge 6 ]; then
        echo -e "${GREEN}✓ Peer discovery working ($total_peers connections)${NC}"
    else
        echo -e "${YELLOW}⚠ Low peer count ($total_peers), may need more time${NC}"
    fi
    
    # Проверяем обмен сообщениями
    echo ""
    echo "Checking message exchange..."
    messages=$(docker logs mesh-node-alpha 2>&1 | grep -c "📨 Сообщение" || echo "0")
    
    if [ $messages -gt 0 ]; then
        echo -e "${GREEN}✓ Messages exchanged ($messages received by alpha)${NC}"
    else
        echo -e "${YELLOW}⚠ No messages detected yet${NC}"
    fi
    
    echo ""
    print_header "Test Complete"
}

cmd_exec() {
    node=${2:-alpha}
    docker exec -it mesh-node-$node bash
}

cmd_send() {
    # Отправить тестовое сообщение
    node=${2:-alpha}
    message=${3:-"Hello from test script"}
    
    echo "Sending message to $node: $message"
    docker exec mesh-node-$node python3 -c "
import asyncio
import sys
sys.path.insert(0, '/app')
from src.network.transport.udp_shaped import ShapedUDPTransport

async def send():
    t = ShapedUDPTransport(local_port=0)
    await t.start()
    await t.send_to(b'$message', ('172.28.0.10', 5000))
    await t.stop()
    print('Sent!')

asyncio.run(send())
"
}

cmd_help() {
    echo "x0tta6bl4 Mesh Network Test Script"
    echo ""
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  build     Build Docker images"
    echo "  up        Start mesh network"
    echo "  down      Stop mesh network"
    echo "  status    Show network status"
    echo "  logs      Show logs (optional: node name)"
    echo "  test      Run integration tests"
    echo "  exec      Open shell in node (default: alpha)"
    echo "  send      Send test message"
    echo "  help      Show this help"
    echo ""
    echo "Examples:"
    echo "  $0 build"
    echo "  $0 up"
    echo "  $0 logs node-alpha"
    echo "  $0 test"
    echo "  $0 exec beta"
}

# Main
case "${1:-help}" in
    build)  cmd_build "$@" ;;
    up)     cmd_up "$@" ;;
    down)   cmd_down "$@" ;;
    logs)   cmd_logs "$@" ;;
    status) cmd_status "$@" ;;
    test)   cmd_test "$@" ;;
    exec)   cmd_exec "$@" ;;
    send)   cmd_send "$@" ;;
    help)   cmd_help ;;
    *)      echo "Unknown command: $1"; cmd_help; exit 1 ;;
esac
