#!/bin/bash
set -e

echo "🔍 x0tta6bl4 Pre-flight Check"
echo "================================"

# Цветовые коды
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_pass=0
check_fail=0

check() {
    if eval "$2"; then
        echo -e "${GREEN}✓${NC} $1"
        ((check_pass++))
    else
        echo -e "${RED}✗${NC} $1"
        ((check_fail++))
    fi
}

# Проверка зависимостей
echo ""
echo "📦 Dependencies:"
check "Docker installed" "command -v docker &> /dev/null"

if command -v docker-compose &> /dev/null; then
    check "Docker Compose installed" "true"
    DOCKER_COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null; then
    check "Docker Compose (plugin) installed" "true"
    DOCKER_COMPOSE_CMD="docker compose"
else
    check "Docker Compose installed" "false"
fi

check "Python 3.8+ installed" "python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,8) else 1)' 2>/dev/null"
check "curl installed" "command -v curl &> /dev/null"

# Проверка прав
echo ""
echo "🔐 Permissions:"
check "Docker daemon running" "docker ps &> /dev/null"
check "Can create containers" "docker run --rm alpine echo 'test' &> /dev/null"

# Проверка портов
echo ""
echo "🔌 Port availability:"
for port in 3000 9090 5001 8001 8002 8003; do
    check "Port $port available" "! nc -z localhost $port 2>/dev/null"
done

# Проверка файловой структуры
echo ""
echo "📁 File structure:"
check "prometheus-config.yml exists" "[ -f monitoring/prometheus-config.yml ]"
check "docker-compose.yml exists" "[ -f docker-compose.yml ]"
check "consciousness.py exists" "[ -f ../src/core/consciousness.py ]"

# Проверка ресурсов системы
echo ""
echo "💻 System resources:"
# Use env var or default for memory check to avoid locale issues with 'free' parsing
total_mem=$(free -m | awk '/^Mem:/{print $2}')
check "RAM >= 4GB" "[ $total_mem -ge 4096 ]"

available_disk=$(df -m . | awk 'NR==2 {print $4}')
check "Free disk >= 10GB" "[ $available_disk -ge 10240 ]"

# Итоговая статистика
echo ""
echo "================================"
if [ $check_fail -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed ($check_pass/$((check_pass+check_fail)))${NC}"
    echo ""
    echo "🚀 Ready to launch x0tta6bl4!"
    echo "   Run: ./quickstart.sh"
    exit 0
else
    echo -e "${YELLOW}⚠ Some checks failed ($check_fail failures)${NC}"
    echo ""
    echo "Please resolve issues above before launching."
    exit 1
fi
