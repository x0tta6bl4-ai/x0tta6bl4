#!/bin/bash
set -e

# Resolve project root (one level up from scripts/)
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

# Compose files
SINGLE_NODE="docker-compose.node.yml"
TESTNET="deploy/docker-compose.yml"

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

if ! command_exists "docker"; then
  echo "Error: Docker is not installed."
  exit 1
fi

usage() {
  echo "x0tta6bl4 Node Deployment"
  echo ""
  echo "Usage: $0 {start|testnet|status|logs|stop|build|clean}"
  echo ""
  echo "  start         Start single node + redis + prometheus"
  echo "  start -m      Start single node + full monitoring (grafana)"
  echo "  testnet       Start 3-node testnet + monitoring"
  echo "  status        Show running services"
  echo "  logs [svc]    Follow logs (optionally for specific service)"
  echo "  stop          Stop all services"
  echo "  build         Build node Docker image"
  echo "  clean         Stop + remove volumes and images"
  exit 1
}

case "$1" in
  start)
    echo "Starting x0tta6bl4 node..."
    if [ "$2" = "-m" ]; then
      docker compose -f "$SINGLE_NODE" --profile monitoring up --build -d
      echo "Node + monitoring started (Grafana: http://localhost:3000)"
    else
      docker compose -f "$SINGLE_NODE" up --build -d
    fi
    echo ""
    echo "  API:        http://localhost:8080"
    echo "  Health:     http://localhost:8080/health"
    echo "  PQC:        http://localhost:8080/pqc/status"
    echo "  Metrics:    http://localhost:8080/metrics"
    echo "  Prometheus: http://localhost:9090"
    ;;
  testnet)
    echo "Starting 3-node x0tta6bl4 testnet..."
    cd deploy
    docker compose up --build -d
    cd "$PROJECT_ROOT"
    echo ""
    echo "  Node 1: http://localhost:8001/health"
    echo "  Node 2: http://localhost:8002/health"
    echo "  Node 3: http://localhost:8003/health"
    echo "  Prometheus: http://localhost:9090"
    echo "  Grafana:    http://localhost:3000"
    ;;
  status)
    echo "=== Single node ==="
    docker compose -f "$SINGLE_NODE" ps 2>/dev/null || true
    echo ""
    echo "=== Testnet ==="
    (cd deploy && docker compose ps 2>/dev/null) || true
    ;;
  logs)
    if [ -n "$2" ]; then
      docker compose -f "$SINGLE_NODE" logs -f "$2" 2>/dev/null || \
        (cd deploy && docker compose logs -f "$2")
    else
      docker compose -f "$SINGLE_NODE" logs -f 2>/dev/null || \
        (cd deploy && docker compose logs -f)
    fi
    ;;
  stop)
    echo "Stopping services..."
    docker compose -f "$SINGLE_NODE" down 2>/dev/null || true
    (cd deploy && docker compose down 2>/dev/null) || true
    echo "Stopped."
    ;;
  build)
    echo "Building x0tta6bl4 node image..."
    docker build -t x0tta6bl4:latest .
    echo "Build complete: x0tta6bl4:latest"
    ;;
  clean)
    echo "Removing all x0tta6bl4 containers, volumes, images..."
    docker compose -f "$SINGLE_NODE" down --volumes --rmi local 2>/dev/null || true
    (cd deploy && docker compose down --volumes --rmi local 2>/dev/null) || true
    echo "Clean."
    ;;
  *)
    usage
    ;;
esac
