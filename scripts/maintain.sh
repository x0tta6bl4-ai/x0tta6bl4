#!/bin/bash
# 🌟 x0tta6bl4 System Maintenance Script
# Автоматическая оптимизация системы

set -e

echo "╔══════════════════════════════════════════════════════════╗"
echo "║        x0tta6bl4 System Maintenance                      ║"
echo "╚══════════════════════════════════════════════════════════╝"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}[1/5]${NC} Docker cleanup..."
docker system prune -f --volumes 2>/dev/null || true

echo -e "${GREEN}[2/5]${NC} Pip cache cleanup..."
pip cache purge 2>/dev/null || true

echo -e "${GREEN}[3/5]${NC} Old temp files cleanup..."
find /tmp -type f -atime +7 -delete 2>/dev/null || true
find ~/.cache -type f -atime +30 -delete 2>/dev/null || true

echo -e "${GREEN}[4/5]${NC} Memory cache drop..."
sync
echo 3 | sudo tee /proc/sys/vm/drop_caches > /dev/null 2>&1 || true

echo -e "${GREEN}[5/5]${NC} Status check..."
echo ""
echo "=== DISK ==="
df -h | grep "^/dev"
echo ""
echo "=== MEMORY ==="
free -h
echo ""
echo "=== LOAD ==="
uptime
echo ""
echo "=== DOCKER ==="
docker system df

echo ""
echo -e "${GREEN}✅ Maintenance complete!${NC}"
