#!/bin/bash
# x0tta6bl4 Lane Manifests & Environment Locking
# Status: VERIFIED HERE

GRN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo "🔒 Locking Lane Manifests..."

# 1. Go Lane Lock
echo -n "🐹 Locking Go Env & Sum... "
go env > .go_env_lock
go mod verify && go mod tidy
if [ $? -eq 0 ]; then
    echo -e "${GRN}[LOCKED]${NC}"
else
    echo -e "${RED}[FAILED]${NC}"
    exit 1
fi

# 2. Python Lane Lock
echo -n "🐍 Locking Python Deps... "
pip freeze > .python_deps_lock
if [ $? -eq 0 ]; then
    echo -e "${GRN}[LOCKED]${NC}"
else
    echo -e "${RED}[FAILED]${NC}"
fi

# 3. DB Lane Lock
echo -n "🗄️  Alembic Preflight... "
if [ -f "alembic.ini" ]; then
    alembic check && echo -e "${GRN}[OK]${NC}" || echo -e "${RED}[DRIFT]${NC}"
else
    echo -e "${GRN}[N/A]${NC}"
fi

echo -e "\n✅ Lane manifests generated. Run before any production-facing task."
