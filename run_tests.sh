#!/bin/bash
# Test Runner Script for x0tta6bl4 v2.0
# ======================================

set -e

echo "🧪 Running x0tta6bl4 v2.0 Tests"
echo "================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if pytest is available
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}❌ pytest not found. Install with: pip install pytest pytest-asyncio${NC}"
    exit 1
fi

# Test directories
TEST_DIRS=(
    "tests/test_pqc_performance.py"
    "tests/test_knowledge_storage.py"
    "tests/test_dao_mapek.py"
    "tests/test_integration_mapek_dao.py"
)

# Run tests
echo -e "${YELLOW}Running unit tests...${NC}"
for test_file in "${TEST_DIRS[@]}"; do
    if [ -f "$test_file" ]; then
        echo ""
        echo -e "${GREEN}Testing: $test_file${NC}"
        pytest "$test_file" -v --tb=short || {
            echo -e "${RED}❌ Tests failed in $test_file${NC}"
            exit 1
        }
    else
        echo -e "${YELLOW}⚠️  Test file not found: $test_file${NC}"
    fi
done

echo ""
echo -e "${GREEN}✅ All tests passed!${NC}"

# Run benchmarks if requested
if [ "$1" == "--benchmark" ]; then
    echo ""
    echo -e "${YELLOW}Running benchmarks...${NC}"
    
    if [ -f "benchmarks/benchmark_pqc.py" ]; then
        echo "📊 PQC Benchmarks:"
        python benchmarks/benchmark_pqc.py
    fi
    
    if [ -f "benchmarks/benchmark_knowledge_storage.py" ]; then
        echo "📊 Knowledge Storage Benchmarks:"
        python benchmarks/benchmark_knowledge_storage.py
    fi
fi

echo ""
echo -e "${GREEN}🎉 Test run completed!${NC}"

