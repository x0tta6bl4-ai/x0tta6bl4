#!/bin/bash

echo "🔍 Полная диагностика контейнеров x0tta6bl4"
echo "=============================================="
echo ""

# Цветовые коды
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Функция для проверки эндпоинта
check_endpoint() {
    local url=$1
    local name=$2
    if curl -sf "$url" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} $name доступен"
        return 0
    else
        echo -e "${RED}✗${NC} $name недоступен"
        return 1
    fi
}

# Получаем все контейнеры
echo -e "${CYAN}📦 Все контейнеры x0tta6bl4:${NC}"
echo ""
docker ps -a --filter "name=x0tta6bl4" --filter "name=mesh-dev" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo ""
echo "=============================================="
echo ""

# Проверяем MESH NODES
echo -e "${BLUE}🔷 MESH NODES${NC}"
echo "----------------------------------------------"

# Updated to check NEW node names as well as old ones for compatibility
NODES_TO_CHECK="x0tta6bl4-node-a x0tta6bl4-node-b x0tta6bl4-node-c x0tta6bl4-node-1 x0tta6bl4-node-2 x0tta6bl4-node-3"

for container in $NODES_TO_CHECK; do
    if docker ps --filter "name=$container" --format "{{.Names}}" | grep -q "$container"; then
        status=$(docker inspect -f '{{.State.Status}}' "$container" 2>/dev/null)
        health=$(docker inspect -f '{{.State.Health.Status}}' "$container" 2>/dev/null)
        uptime=$(docker inspect -f '{{.State.StartedAt}}' "$container" 2>/dev/null)
        
        echo ""
        echo -e "${GREEN}✅ $container${NC}"
        echo "   Status: $status"
        if [ "$health" != "<no value>" ]; then
            echo "   Health: $health"
        fi
        echo "   Started: $uptime"
        
        # Получаем порт - trying both 8000 (internal) mapping
        port=$(docker port "$container" 2>/dev/null | grep -E "8000/tcp|8080/tcp" | cut -d':' -f2)
        
        if [ ! -z "$port" ]; then
            echo "   Port: $port"
            
            # Проверяем метрики
            echo "   Checking metrics..."
            if curl -sf "http://localhost:$port/metrics" > /dev/null 2>&1; then
                # Проверяем наличие consciousness метрик
                consciousness_count=$(curl -s "http://localhost:$port/metrics" | grep -c "consciousness" || echo "0")
                
                if [ "$consciousness_count" -gt 0 ]; then
                    echo -e "   ${GREEN}✓${NC} Consciousness metrics: $consciousness_count found"
                    
                    # Выводим φ-ratio если есть
                    phi_ratio=$(curl -s "http://localhost:$port/metrics" | grep "consciousness_phi_ratio" | awk '{print $2}')
                    if [ ! -z "$phi_ratio" ]; then
                        echo "   φ-ratio: $phi_ratio"
                    fi
                    
                    # Выводим состояние
                    state=$(curl -s "http://localhost:$port/metrics" | grep "consciousness_state" | awk '{print $2}')
                    if [ ! -z "$state" ]; then
                        case ${state%.*} in
                            4) state_name="EUPHORIC" ;;
                            3) state_name="HARMONIC" ;;
                            2) state_name="CONTEMPLATIVE" ;;
                            1) state_name="MYSTICAL" ;;
                            *) state_name="UNKNOWN" ;;
                        esac
                        echo "   State: $state_name ($state)"
                    fi
                else
                    echo -e "   ${YELLOW}⚠${NC} No consciousness metrics found (old version?)"
                fi
            else
                echo -e "   ${RED}✗${NC} Metrics endpoint unavailable"
            fi
        fi
    else
        # Don't print error for old nodes if they are expected to be gone
        if [[ "$container" != *"node-a"* && "$container" != *"node-b"* && "$container" != *"node-c"* ]]; then
             echo -e "${RED}❌ $container${NC} - not running"
        fi
    fi
done

# Проверяем MONITORING
echo ""
echo ""
echo -e "${BLUE}📊 MONITORING STACK${NC}"
echo "----------------------------------------------"

# Prometheus
if docker ps --filter "name=x0tta6bl4-prometheus" --format "{{.Names}}" | grep -q "prometheus"; then
    echo ""
    echo -e "${GREEN}✅ x0tta6bl4-prometheus${NC}"
    prom_port=$(docker port x0tta6bl4-prometheus 2>/dev/null | grep "9090/tcp" | cut -d':' -f2)
    echo "   Port: $prom_port"
    check_endpoint "http://localhost:$prom_port/-/healthy" "Prometheus"
    
    # Проверяем targets
    targets=$(curl -s "http://localhost:$prom_port/api/v1/targets" 2>/dev/null | jq -r '.data.activeTargets | length' 2>/dev/null || echo "unknown")
    echo "   Active targets: $targets"
fi

# Grafana
if docker ps --filter "name=x0tta6bl4-grafana" --format "{{.Names}}" | grep -q "grafana"; then
    echo ""
    echo -e "${GREEN}✅ x0tta6bl4-grafana${NC}"
    grafana_port=$(docker port x0tta6bl4-grafana 2>/dev/null | grep "3000/tcp" | cut -d':' -f2)
    echo "   Port: $grafana_port"
    check_endpoint "http://localhost:$grafana_port/api/health" "Grafana"
    echo "   URL: http://localhost:$grafana_port"
fi

# Agent1
if docker ps --filter "name=agent1-monitoring" --format "{{.Names}}" | grep -q "agent1"; then
    echo ""
    echo -e "${GREEN}✅ agent1-monitoring${NC}"
    agent_port=$(docker port agent1-monitoring 2>/dev/null | grep "8000/tcp" | cut -d':' -f2)
    echo "   Port: $agent_port"
    check_endpoint "http://localhost:$agent_port/health" "Agent1"
fi

# INFRASTRUCTURE
echo ""
echo ""
echo -e "${BLUE}🏗️ INFRASTRUCTURE${NC}"
echo "----------------------------------------------"

# Redis
if docker ps -a --filter "name=redis" --format "{{.Names}}" | grep -q "redis"; then
    redis_container=$(docker ps -a --filter "name=redis" --format "{{.Names}}" | head -1)
    echo ""
    echo -e "${GREEN}✅ $redis_container${NC}"
    redis_status=$(docker inspect -f '{{.State.Status}}' "$redis_container")
    echo "   Status: $redis_status"
fi

# IPFS
if docker ps -a --filter "name=ipfs" --format "{{.Names}}" | grep -q "ipfs"; then
    ipfs_container=$(docker ps -a --filter "name=ipfs" --format "{{.Names}}" | head -1)
    echo ""
    echo -e "${GREEN}✅ $ipfs_container${NC}"
    ipfs_status=$(docker inspect -f '{{.State.Status}}' "$ipfs_container")
    echo "   Status: $ipfs_status"
    
    ipfs_port=$(docker port "$ipfs_container" 2>/dev/null | grep "5001/tcp" | cut -d':' -f2)
    if [ ! -z "$ipfs_port" ]; then
        echo "   API Port: $ipfs_port"
    fi
fi

# KUBERNETES
echo ""
echo ""
echo -e "${BLUE}☸️ KUBERNETES CLUSTER (Kind)${NC}"
echo "----------------------------------------------"
k8s_nodes=$(docker ps --filter "name=mesh-dev" --format "{{.Names}}")
if [ ! -z "$k8s_nodes" ]; then
    k8s_count=$(echo "$k8s_nodes" | wc -l)
    echo ""
    echo -e "${GREEN}✅ Kubernetes cluster active${NC}"
    echo "   Nodes: $k8s_count"
    echo "$k8s_nodes" | while read node; do
        echo "   - $node"
    done
    
    # Проверяем kubectl доступ
    if command -v kubectl &> /dev/null; then
        echo ""
        echo "   Checking cluster..."
        kubectl cluster-info --context kind-mesh-dev 2>/dev/null | head -2 || echo "   kubectl context not configured"
    fi
else
    echo -e "${YELLOW}⚠${NC} No Kubernetes nodes found"
fi

# СВОДКА
echo ""
echo ""
echo "=============================================="
echo -e "${PURPLE}📈 СВОДКА${NC}"
echo "=============================================="

total=$(docker ps --filter "name=x0tta6bl4" --filter "name=mesh-dev" --format "{{.Names}}" | wc -l)
running=$(docker ps --filter "name=x0tta6bl4" --filter "name=mesh-dev" --filter "status=running" --format "{{.Names}}" | wc -l)
nodes=$(docker ps --filter "name=x0tta6bl4-node" --filter "status=running" --format "{{.Names}}" | wc -l)

echo ""
echo "Всего контейнеров: $total"
echo "Запущено: $running"
echo "Mesh nodes: $nodes"

if [ $nodes -ge 3 ]; then
    echo -e "${GREEN}✓ All mesh nodes operational${NC}"
else
    echo -e "${YELLOW}⚠ Expected at least 3 nodes, found $nodes${NC}"
fi

# Quick consciousness check
echo ""
echo "=============================================="
echo -e "${CYAN}🧠 CONSCIOUSNESS STATUS${NC}"
echo "=============================================="
echo ""

# Checking extended range of ports to cover both old and new configurations
for port in 8000 8001 8002 8003; do
    node_name=""
    case $port in
        8000) node_name="node-a (legacy)" ;;
        8001) node_name="node-1" ;;
        8002) node_name="node-2" ;;
        8003) node_name="node-3" ;;
    esac
    
    if [ -n "$node_name" ]; then
        if curl -sf "http://localhost:$port/metrics" > /dev/null 2>&1; then
            phi=$(curl -s "http://localhost:$port/metrics" | grep "consciousness_phi_ratio" | awk '{print $2}')
            state=$(curl -s "http://localhost:$port/metrics" | grep "consciousness_state" | awk '{print $2}')
            
            if [ ! -z "$phi" ]; then
                case ${state%.*} in
                    4) state_name="EUPHORIC" emoji="✨" ;;
                    3) state_name="HARMONIC" emoji="🌟" ;;
                    2) state_name="CONTEMPLATIVE" emoji="🤔" ;;
                    1) state_name="MYSTICAL" emoji="🔮" ;;
                    *) state_name="UNKNOWN" emoji="❓" ;;
                esac
                echo -e "${emoji} ${GREEN}$node_name${NC}: φ=$phi | $state_name"
            else
                echo -e "${YELLOW}⚠ $node_name${NC}: No consciousness metrics (legacy version)"
            fi
        else
            # Only report failure for new expected nodes
            if [[ $port -ne 8000 ]]; then
                echo -e "${RED}✗ $node_name${NC}: Unreachable"
            fi
        fi
    fi
done

echo ""
echo "=============================================="

