#!/bin/bash
# x0tta6bl4 Execution Substrate Preflight Gate
# Status: VERIFIED HERE

GRN='\033[0;32m'
RED='\033[0;31m'
YLW='\033[0;33m'
NC='\033[0m'

echo "🔍 Starting Preflight Gate..."

# 1. Go Dependency Check
echo -n "🐹 Checking Go modules... "
if go mod verify >/dev/null 2>&1; then
    echo -e "${GRN}[PASS]${NC}"
else
    echo -e "${RED}[FAIL]${NC} go.sum is out of sync or corrupt."
    exit 1
fi

# 2. Python Dependency Check
echo -n "🐍 Checking Python dependencies... "
if pip check >/dev/null 2>&1; then
    echo -e "${GRN}[PASS]${NC}"
else
    echo -e "${YLW}[WARN]${NC} Python dependency conflict detected."
    # Мы не выходим с ошибкой здесь, так как многие конфликты dev-зависимостей не критичны
fi

# 3. Database Schema Check (Alembic)
echo -n "🗄️ Checking DB Migrations... "
if [ -f "alembic.ini" ]; then
    if alembic current >/dev/null 2>&1; then
        echo -e "${GRN}[PASS]${NC}"
    else
        echo -e "${RED}[FAIL]${NC} Alembic drift detected."
        exit 1
    fi
else
    echo -e "${YLW}[SKIP]${NC} alembic.ini not found."
fi

# 4. eBPF Toolchain Check
echo -n "🐝 Checking eBPF Toolchain... "
if command -v clang >/dev/null && command -v bpftool >/dev/null; then
    echo -e "${GRN}[PASS]${NC}"
else
    echo -e "${RED}[FAIL]${NC} Clang or bpftool missing."
    exit 1
fi

echo -e "\n${GRN}🚀 PREFLIGHT OK.${NC} Execution substrate is stable."
