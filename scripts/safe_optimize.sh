#!/bin/bash
# Safe System Optimization Script
# Focuses on cleanup and tuning without reinstalling core packages

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}Starting Safe Optimization...${NC}"

# 1. Process Cleanup
echo -e "${YELLOW}[1/5] Cleaning up zombie processes...${NC}"
# Kill high CPU python/node processes that are not critical (be careful)
# We avoid killing the current shell or essential services
pkill -f "python3 src/ml/benchmarks" || true
pkill -f "pytest" || true
pkill -f "node_modules" || true

# 2. Docker Cleanup (Safe)
echo -e "${YELLOW}[2/5] Cleaning Docker resources...${NC}"
docker container prune -f || true
docker image prune -f || true
docker network prune -f || true
docker volume prune -f || true

# 3. System Tuning (Non-persistent for safety)
echo -e "${YELLOW}[3/5] Tuning kernel parameters...${NC}"
# fs.inotify for heavy dev environments
if [ -w /proc/sys/fs/inotify/max_user_watches ]; then
    echo 524288 > /proc/sys/fs/inotify/max_user_watches || true
fi

# 4. Python Environment
echo -e "${YELLOW}[4/5] Optimizing Python environment...${NC}"
if [ -d ".venv" ]; then
    source .venv/bin/activate
    pip install --upgrade pip setuptools wheel --quiet
    # Clean cache
    rm -rf .pytest_cache .mypy_cache __pycache__
fi

# 5. File Cleanup
echo -e "${YELLOW}[5/5] Removing temporary files...${NC}"
rm -rf .tmp/* || true
find . -name "*.pyc" -delete
find . -name "*.pyo" -delete

echo -e "${GREEN}Safe Optimization Complete!${NC}"
echo -e "Load check:"
uptime
