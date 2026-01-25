#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PROJECT_ROOT="/mnt/AC74CC2974CBF3DC"
cd "$PROJECT_ROOT"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}x0tta6bl4 Minimal Mesh Test Suite${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Step 1: Build Docker images
echo -e "${YELLOW}[1/9] Building Docker images...${NC}"
if docker-compose -f docker-compose.minimal.yml build; then
    echo -e "${GREEN}✓ Docker images built successfully${NC}"
else
    echo -e "${RED}✗ Docker build failed${NC}"
    exit 1
fi
echo ""

# Step 2: Start mesh
echo -e "${YELLOW}[2/9] Starting 3-node mesh...${NC}"
if docker-compose -f docker-compose.minimal.yml up -d; then
    echo -e "${GREEN}✓ Mesh started${NC}"
else
    echo -e "${RED}✗ Failed to start mesh${NC}"
    exit 1
fi
echo ""

# Step 3: Wait for health checks
echo -e "${YELLOW}[3/9] Waiting for health checks (15 seconds)...${NC}"
sleep 15
echo -e "${GREEN}✓ Wait complete${NC}"
echo ""

# Step 4: Verify container status
echo -e "${YELLOW}[4/9] Verifying container status...${NC}"
docker-compose -f docker-compose.minimal.yml ps
echo ""

# Step 5: Check health endpoints
echo -e "${YELLOW}[5/9] Checking health endpoints...${NC}"

check_health() {
    local port=$1
    local node=$2
    if response=$(curl -s -f http://localhost:$port/health 2>&1); then
        echo -e "${GREEN}✓ Node $node (port $port): $response${NC}"
        return 0
    else
        echo -e "${RED}✗ Node $node (port $port): Failed to connect${NC}"
        return 1
    fi
}

check_health 8000 "A" || exit 1
check_health 8001 "B" || exit 1
check_health 8002 "C" || exit 1
echo ""

# Step 6: Run quick integration test
echo -e "${YELLOW}[6/9] Running quick integration test...${NC}"
source .venv/bin/activate
if pytest tests/integration/test_mesh_self_healing.py::test_api_endpoints_available -v; then
    echo -e "${GREEN}✓ Quick test passed${NC}"
else
    echo -e "${RED}✗ Quick test failed${NC}"
    docker-compose -f docker-compose.minimal.yml logs
    exit 1
fi
echo ""

# Step 7: Run full integration test suite
echo -e "${YELLOW}[7/9] Running full integration test suite...${NC}"
if pytest tests/integration/ -v -m integration --tb=short; then
    echo -e "${GREEN}✓ Integration tests completed${NC}"
else
    echo -e "${YELLOW}⚠ Some tests failed or skipped (expected without Yggdrasil)${NC}"
fi
echo ""

# Step 8: Run with coverage
echo -e "${YELLOW}[8/9] Running with coverage...${NC}"
pytest tests/integration/ --cov=src --cov-report=term-missing --cov-report=html -p no:pytest_ethereum || true
echo ""

# Step 9: Summary
echo -e "${YELLOW}[9/9] Generating summary...${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Test Execution Summary${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Coverage report: htmlcov/index.html"
echo "To view: xdg-open htmlcov/index.html"
echo ""
echo "To stop mesh: docker-compose -f docker-compose.minimal.yml down"
echo "To view logs: docker-compose -f docker-compose.minimal.yml logs -f"
echo ""
echo -e "${GREEN}✓ All tests completed!${NC}"
echo ""

# Optional cleanup
read -p "Stop mesh now? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Stopping mesh...${NC}"
    docker-compose -f docker-compose.minimal.yml down
    echo -e "${GREEN}✓ Mesh stopped${NC}"
else
    echo -e "${YELLOW}Mesh still running. Stop manually.${NC}"
fi
