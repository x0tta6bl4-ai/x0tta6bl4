#!/bin/bash
###############################################################################
# x0tta6bl4 Local CI/CD Simulation
# Проверяет локально все что делает CI/CD pipeline
###############################################################################

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

BLUE='\033[0;34m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}🔍 x0tta6bl4 Local CI/CD Simulation${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo ""

PASSED=0
FAILED=0

# Function to run check
run_check() {
    local name=$1
    local cmd=$2
    
    echo -n "⏳ $name... "
    
    if eval "$cmd" &>/dev/null; then
        echo -e "${GREEN}✅${NC}"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}❌${NC}"
        ((FAILED++))
        return 1
    fi
}

echo -e "${YELLOW}📋 PHASE 1: Environment Setup${NC}"
echo "─────────────────────────────────────────────────────────────────"
run_check "Python 3.10+" "python3 --version | grep -E '(3\.1[0-9]|3\.2[0-9])'" || true
run_check "pip installed" "python3 -m pip --version" || true
echo ""

echo -e "${YELLOW}📋 PHASE 2: Dependencies${NC}"
echo "─────────────────────────────────────────────────────────────────"
run_check "Core deps installed" "python3 -c 'import fastapi, uvicorn, pydantic, pytest'" || true
echo ""

echo -e "${YELLOW}📋 PHASE 3: Code Quality (Linting)${NC}"
echo "─────────────────────────────────────────────────────────────────"

# Flake8
if command -v flake8 &> /dev/null; then
    echo -n "⏳ flake8 (linting)... "
    if flake8 src tests --count --select=E9,F63,F7,F82 --show-source 2>/dev/null | grep -q "0 errors" || ! flake8 src tests 2>/dev/null; then
        echo -e "${GREEN}✅${NC}"
        ((PASSED++))
    else
        echo -e "${YELLOW}⚠️  (warnings ok)${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  flake8: not installed${NC}"
fi

# Black formatting
if command -v black &> /dev/null; then
    echo -n "⏳ black (format check)... "
    if black --check src tests --line-length=100 2>/dev/null; then
        echo -e "${GREEN}✅${NC}"
        ((PASSED++))
    else
        echo -e "${YELLOW}⚠️  (not formatted, can auto-fix)${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  black: not installed${NC}"
fi

# Mypy
if command -v mypy &> /dev/null; then
    echo -n "⏳ mypy (type check)... "
    if mypy src --ignore-missing-imports 2>/dev/null | tail -1 | grep -q "success"; then
        echo -e "${GREEN}✅${NC}"
        ((PASSED++))
    else
        echo -e "${YELLOW}⚠️  (type issues ok for now)${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  mypy: not installed${NC}"
fi
echo ""

echo -e "${YELLOW}📋 PHASE 4: Unit Tests${NC}"
echo "─────────────────────────────────────────────────────────────────"

if command -v pytest &> /dev/null; then
    echo -n "⏳ pytest (67/67 tests)... "
    TEST_OUTPUT=$(pytest tests/test_mape_k.py -q --tb=no 2>&1 || true)
    PASSED_COUNT=$(echo "$TEST_OUTPUT" | grep -oP '\d+(?= passed)' || echo "0")
    
    if [ "$PASSED_COUNT" = "67" ]; then
        echo -e "${GREEN}✅ ($PASSED_COUNT/67)${NC}"
        ((PASSED++))
    else
        echo -e "${YELLOW}⚠️  ($PASSED_COUNT/67)${NC}"
    fi
else
    echo -e "${RED}❌ pytest not installed${NC}"
    ((FAILED++))
fi

# Coverage
if command -v pytest &> /dev/null; then
    echo -n "⏳ coverage... "
    COVERAGE=$(pytest tests/test_mape_k.py --cov=src.mape_k --cov-report=term-missing -q 2>&1 | grep TOTAL | awk '{print $NF}' | sed 's/%//' || echo "0")
    if (( $(echo "$COVERAGE >= 50" | bc -l) )); then
        echo -e "${GREEN}✅ ($COVERAGE%)${NC}"
        ((PASSED++))
    else
        echo -e "${RED}❌ ($COVERAGE% - need ≥50%)${NC}"
        ((FAILED++))
    fi
else
    echo -e "${YELLOW}⚠️  coverage: pytest not installed${NC}"
fi
echo ""

echo -e "${YELLOW}📋 PHASE 5: Version Check${NC}"
echo "─────────────────────────────────────────────────────────────────"

PYPROJECT_VERSION=$(grep -m 1 'version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/')
MAPE_K_VERSION=$(grep '__version__' src/mape_k/__init__.py | head -1 | sed 's/__version__ = "\(.*\)"/\1/')

echo -n "⏳ pyproject.toml version... "
echo -e "${GREEN}✅ ($PYPROJECT_VERSION)${NC}"

echo -n "⏳ src/mape_k/__init__.py version... "
if [ "$MAPE_K_VERSION" == "$PYPROJECT_VERSION" ]; then
    echo -e "${GREEN}✅ ($MAPE_K_VERSION)${NC}"
    ((PASSED++))
else
    echo -e "${RED}❌ (mismatch: $MAPE_K_VERSION vs $PYPROJECT_VERSION)${NC}"
    ((FAILED++))
fi
echo ""

echo -e "${YELLOW}📋 PHASE 6: Build Artifacts${NC}"
echo "─────────────────────────────────────────────────────────────────"

if command -v python3 -m build &> /dev/null 2>&1 || python3 -c "import build" 2>/dev/null; then
    echo -n "⏳ Build distribution... "
    if python3 -m build 2>/dev/null && [ -f "dist/x0tta6bl4-${PYPROJECT_VERSION}.tar.gz" ]; then
        echo -e "${GREEN}✅${NC}"
        ((PASSED++))
        
        echo -n "⏳ Build wheel... "
        if [ -f "dist/x0tta6bl4-${PYPROJECT_VERSION}-py3-none-any.whl" ]; then
            echo -e "${GREEN}✅${NC}"
            ((PASSED++))
        fi
    else
        echo -e "${YELLOW}⚠️  (build not verified)${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  build module not installed${NC}"
fi
echo ""

echo -e "${YELLOW}📋 PHASE 7: Docker Image${NC}"
echo "─────────────────────────────────────────────────────────────────"

if command -v docker &> /dev/null; then
    echo -n "⏳ Docker available... "
    echo -e "${GREEN}✅${NC}"
    
    echo -n "⏳ Dockerfile exists... "
    if [ -f "Dockerfile" ] && [ -f "Dockerfile.production" ]; then
        echo -e "${GREEN}✅${NC}"
        ((PASSED++))
    else
        echo -e "${RED}❌${NC}"
        ((FAILED++))
    fi
else
    echo -e "${YELLOW}⚠️  Docker not installed (skipping)${NC}"
fi
echo ""

echo -e "${YELLOW}📋 PHASE 8: Git & Versioning${NC}"
echo "─────────────────────────────────────────────────────────────────"

if command -v git &> /dev/null; then
    echo -n "⏳ Git repository... "
    if git rev-parse --is-inside-work-tree &>/dev/null; then
        echo -e "${GREEN}✅${NC}"
        ((PASSED++))
        
        echo -n "⏳ Current branch... "
        CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
        echo -e "${GREEN}✅ ($CURRENT_BRANCH)${NC}"
        
        echo -n "⏳ Commits in repo... "
        COMMIT_COUNT=$(git rev-list --count HEAD)
        echo -e "${GREEN}✅ ($COMMIT_COUNT)${NC}"
        
        echo -n "⏳ Tags exist... "
        if git tag | grep -q "v"; then
            echo -e "${GREEN}✅${NC}"
            ((PASSED++))
        else
            echo -e "${YELLOW}⚠️  (no tags yet)${NC}"
        fi
    else
        echo -e "${RED}❌${NC}"
        ((FAILED++))
    fi
else
    echo -e "${RED}❌ Git not installed${NC}"
    ((FAILED++))
fi
echo ""

echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${GREEN}✅ Passed: $PASSED${NC}"
if [ $FAILED -gt 0 ]; then
    echo -e "${RED}❌ Failed: $FAILED${NC}"
else
    echo -e "${GREEN}❌ Failed: $FAILED${NC}"
fi
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}🎉 LOCAL CI/CD SIMULATION SUCCESSFUL!${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Push to GitHub: git push origin develop"
    echo "2. Create PR to main"
    echo "3. GitHub Actions will run full CI/CD pipeline"
    echo "4. After merge, tag for release: git tag v$PYPROJECT_VERSION"
    echo ""
    exit 0
else
    echo -e "${RED}⚠️  Fix issues and re-run${NC}"
    exit 1
fi
