#!/bin/bash
# 🔍 x0tta6bl4 v1.0.0 COMPREHENSIVE VALIDATION SCRIPT
# Complete verification from Phase 1 to Post-Migration Enhancement


RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PASSED=0
FAILED=0

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  x0tta6bl4 v1.0.0 - COMPREHENSIVE VALIDATION SUITE        ║${NC}"
echo -e "${BLUE}║  Testing all phases from Phase 1 to Enhancement Layer    ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}\n"

# Helper functions
check_passed() {
    echo -e "${GREEN}✅ PASSED:${NC} $1"
    ((PASSED++))
}

check_failed() {
    echo -e "${RED}❌ FAILED:${NC} $1"
    ((FAILED++))
}

section() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
}

# ============================================================================
# PHASE 1: ARCHIVE CLEANUP
# ============================================================================
section "PHASE 1: Archive Cleanup Validation"

if [ -d "archive/legacy" ]; then
    check_passed "archive/legacy/ directory exists"
else
    check_failed "archive/legacy/ directory missing"
fi

if [ -d "archive/artifacts" ] || [ -d "archive/legacy/artifacts" ]; then
    check_passed "archive/artifacts/ directory exists"
else
    echo -e "${YELLOW}⚠️  SKIPPED:${NC} archive/artifacts/ not found (optional)"
fi

if [ -d "archive/snapshots" ] || [ -d "archive/legacy/snapshots" ]; then
    check_passed "archive/snapshots/ directory exists"
else
    echo -e "${YELLOW}⚠️  SKIPPED:${NC} archive/snapshots/ not found (optional)"
fi

if git log --oneline | grep -q "e5560bd.*Archive cleanup"; then
    check_passed "Phase 1 commit found: e5560bd"
else
    check_failed "Phase 1 commit not found"
fi

# ============================================================================
# PHASE 2: INFRASTRUCTURE CONSOLIDATION
# ============================================================================
section "PHASE 2: Infrastructure Consolidation Validation"

INFRA_DIRS=$(find infra -maxdepth 1 -type d 2>/dev/null | wc -l)
if [ "$INFRA_DIRS" -ge 5 ]; then
    check_passed "infra/ contains ≥5 subdirectories (networking, security, k8s, docker, terraform)"
else
    check_failed "infra/ missing expected subdirectories (found $INFRA_DIRS)"
fi

if [ -f "infra/README.md" ]; then
    check_passed "infra/README.md exists"
else
    check_failed "infra/README.md missing"
fi

NETWORK_FILES=$(find infra -type f -name "*network*" -o -name "*batman*" 2>/dev/null | wc -l)
if [ "$NETWORK_FILES" -gt 0 ]; then
    check_passed "Networking files found ($NETWORK_FILES files)"
else
    check_failed "Networking files missing"
fi

if git log --oneline | grep -qE "(5be2154|5028035).*Infrastructure"; then
    check_passed "Phase 2 commits found"
else
    check_failed "Phase 2 commits not found"
fi

# ============================================================================
# PHASE 3: DEPENDENCY CONSOLIDATION
# ============================================================================
section "PHASE 3: Dependency Consolidation Validation"

if [ -f "pyproject.toml" ]; then
    check_passed "pyproject.toml exists"
else
    check_failed "pyproject.toml missing - CRITICAL"
fi

if grep -q "\[project.optional-dependencies\]" pyproject.toml 2>/dev/null; then
    check_passed "pyproject.toml contains optional-dependencies section"
else
    check_failed "pyproject.toml missing optional-dependencies"
fi

REQ_FILES=$(find . -name "requirements*.txt" -not -path "./archive/*" 2>/dev/null | wc -l)
if [ "$REQ_FILES" -le 2 ]; then
    check_passed "Requirements files consolidated ($REQ_FILES remaining)"
else
    check_failed "Found $REQ_FILES remaining requirements files (expected ≤2)"
fi

if git log --oneline | grep -q "4e4f65b.*Dependency"; then
    check_passed "Phase 3 commit found: 4e4f65b"
else
    check_failed "Phase 3 commit not found"
fi

# ============================================================================
# PHASE 4: CODE STRUCTURE
# ============================================================================
section "PHASE 4: Code Restructuring Validation"

SRC_DIRS=("core" "security" "network" "ml" "monitoring" "adapters")
for dir in "${SRC_DIRS[@]}"; do
    if [ -d "src/$dir" ]; then
        check_passed "src/$dir/ exists"
    else
        check_failed "src/$dir/ missing"
    fi
done

TEST_DIRS=("unit" "integration" "security" "performance")
for dir in "${TEST_DIRS[@]}"; do
    if [ -d "tests/$dir" ]; then
        check_passed "tests/$dir/ exists"
    else
        check_failed "tests/$dir/ missing"
    fi
done

if [ -f "src/core/__init__.py" ]; then
    check_passed "src/core/__init__.py exists (Python package)"
else
    check_failed "src/core/__init__.py missing"
fi

if git log --oneline | grep -q "8a67e41.*restructuring"; then
    check_passed "Phase 4 commit found: 8a67e41"
else
    check_failed "Phase 4 commit not found"
fi

# ============================================================================
# PHASE 5: CI/CD SETUP
# ============================================================================
section "PHASE 5: CI/CD Setup Validation"

WORKFLOWS=("ci.yml" "security-scan.yml" "benchmarks.yml" "release.yml")
for workflow in "${WORKFLOWS[@]}"; do
    if [ -f ".github/workflows/$workflow" ]; then
        check_passed ".github/workflows/$workflow exists"
    else
        check_failed ".github/workflows/$workflow missing"
    fi
done

if [ -f "pytest.ini" ]; then
    check_passed "pytest.ini exists"
else
    check_failed "pytest.ini missing"
fi

if grep -q "coverage" pytest.ini 2>/dev/null; then
    check_passed "pytest.ini includes coverage configuration"
else
    check_failed "pytest.ini missing coverage config"
fi

if git log --oneline | grep -q "d78dced.*CI/CD"; then
    check_passed "Phase 5 commit found: d78dced"
else
    check_failed "Phase 5 commit not found"
fi

# ============================================================================
# PHASE 6: COPILOT OPTIMIZATION
# ============================================================================
section "PHASE 6: Copilot Optimization Validation"

if [ -f ".copilot.yaml" ]; then
    check_passed ".copilot.yaml exists"
else
    check_failed ".copilot.yaml missing"
fi

if [ -f "docs/COPILOT_PROMPTS.md" ]; then
    check_passed "docs/COPILOT_PROMPTS.md exists"
else
    check_failed "docs/COPILOT_PROMPTS.md missing"
fi

PROMPTS_LINES=$(wc -l < docs/COPILOT_PROMPTS.md 2>/dev/null || echo 0)
if [ "$PROMPTS_LINES" -gt 200 ]; then
    check_passed "COPILOT_PROMPTS.md comprehensive ($PROMPTS_LINES lines)"
else
    check_failed "COPILOT_PROMPTS.md too short"
fi

if git log --oneline | grep -q "d77f162.*Copilot"; then
    check_passed "Phase 6 commit found: d77f162"
else
    check_failed "Phase 6 commit not found"
fi

# ============================================================================
# PHASE 7: PRODUCTION ROLLOUT
# ============================================================================
section "PHASE 7: Production Rollout Validation"

if [ -f "CHANGELOG.md" ]; then
    check_passed "CHANGELOG.md exists"
else
    check_failed "CHANGELOG.md missing"
fi

CHANGELOG_LINES=$(wc -l < CHANGELOG.md 2>/dev/null || echo 0)
if [ "$CHANGELOG_LINES" -gt 100 ]; then
    check_passed "CHANGELOG.md comprehensive ($CHANGELOG_LINES lines)"
else
    check_failed "CHANGELOG.md too short ($CHANGELOG_LINES lines)"
fi

if [ -f "MIGRATION_PROGRESS.md" ]; then
    check_passed "MIGRATION_PROGRESS.md exists"
else
    check_failed "MIGRATION_PROGRESS.md missing"
fi

if git tag | grep -q "v1.0.0-restructured"; then
    check_passed "Git tag v1.0.0-restructured exists"
else
    check_failed "Git tag v1.0.0-restructured missing"
fi

if git log --oneline | grep -qE "(65bf62f|43004bb).*Phase 7"; then
    check_passed "Phase 7 commits found"
else
    check_failed "Phase 7 commits not found"
fi

# ============================================================================
# POST-MIGRATION: FOUNDATIONAL LAYER
# ============================================================================
section "POST-MIGRATION: Foundational Layer Validation"

DOCS=("README.md" "CONTRIBUTING.md" "SECURITY.md" "ROADMAP.md")
for doc in "${DOCS[@]}"; do
    if [ -f "$doc" ]; then
        check_passed "$doc exists"
    else
        check_failed "$doc missing"
    fi
done

if [ -f "src/core/app.py" ]; then
    check_passed "src/core/app.py (FastAPI scaffold) exists"
else
    check_failed "src/core/app.py missing"
fi

if [ -f "src/core/health.py" ]; then
    check_passed "src/core/health.py (health utility) exists"
else
    check_failed "src/core/health.py missing"
fi

if [ -f "tests/unit/test_health.py" ]; then
    check_passed "tests/unit/test_health.py (unit test) exists"
else
    check_failed "tests/unit/test_health.py missing"
fi

if git log --oneline | grep -q "30d553c.*Post-migration"; then
    check_passed "Post-migration enhancement commit found: 30d553c"
else
    check_failed "Post-migration enhancement commit not found"
fi

# ============================================================================
# ROADMAP & ISSUE TEMPLATES
# ============================================================================
section "ROADMAP & ISSUE TEMPLATES VALIDATION"

if [ -f ".github/ISSUE_TEMPLATE/bug_report.yml" ]; then
    check_passed "Bug report template exists"
else
    check_failed "Bug report template missing"
fi

if [ -f ".github/ISSUE_TEMPLATE/feature_request.yml" ]; then
    check_passed "Feature request template exists"
else
    check_failed "Feature request template missing"
fi

if [ -f ".github/ISSUE_TEMPLATE/config.yml" ]; then
    check_passed "Issue template config exists"
else
    check_failed "Issue template config missing"
fi

if git log --oneline | grep -q "7fcb24e.*roadmap"; then
    check_passed "Roadmap commit found: 7fcb24e"
else
    check_failed "Roadmap commit not found"
fi

# ============================================================================
# FUNCTIONAL TESTS
# ============================================================================
section "FUNCTIONAL TESTS"

# Test pyproject.toml syntax
if python3 -c "import tomllib; tomllib.load(open('pyproject.toml', 'rb'))" 2>/dev/null; then
    check_passed "pyproject.toml syntax is valid"
else
    check_failed "pyproject.toml syntax error"
fi

# Test Python imports (health module)
if python3 -c "from src.core.health import get_health" 2>/dev/null; then
    check_passed "src.core.health module imports correctly"
else
    check_failed "src.core.health import failed"
fi

# Test app structure
if grep -q "FastAPI" src/core/app.py 2>/dev/null; then
    check_passed "src/core/app.py contains FastAPI app"
else
    check_failed "src/core/app.py missing FastAPI"
fi

# Test health endpoint logic
if python3 -c "from src.core.health import get_health; assert get_health()['status'] == 'ok'" 2>/dev/null; then
    check_passed "Health check returns expected status"
else
    check_failed "Health check logic incorrect"
fi

# ============================================================================
# GIT HISTORY VALIDATION
# ============================================================================
section "GIT HISTORY & COMMITS"

PHASE_COMMITS=$(git log --oneline | grep -cE "(Phase [1-7]|Archive|Infrastructure|Dependency|restructuring|CI/CD|Copilot|Production|Post-migration|roadmap)" || echo 0)
if [ "$PHASE_COMMITS" -ge 10 ]; then
    check_passed "Found $PHASE_COMMITS migration commits (expecting ≥10)"
else
    check_failed "Only found $PHASE_COMMITS migration commits (expected ≥10)"
fi

if git tag | grep -q "v0.9.5-pre-restructure"; then
    check_passed "Rollback point v0.9.5-pre-restructure exists"
else
    check_failed "Rollback point missing"
fi

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$CURRENT_BRANCH" = "main" ]; then
    check_passed "Currently on main branch"
else
    check_failed "Not on main branch (on: $CURRENT_BRANCH)"
fi

# ============================================================================
# REPOSITORY METRICS
# ============================================================================
section "REPOSITORY METRICS"

REPO_SIZE=$(du -sh . 2>/dev/null | cut -f1 || echo "unknown")
echo "📊 Repository size: $REPO_SIZE"

COMMIT_COUNT=$(git rev-list --all --count 2>/dev/null || echo "unknown")
echo "📊 Total commits: $COMMIT_COUNT"

TAG_COUNT=$(git tag | wc -l)
echo "📊 Git tags: $TAG_COUNT"

if [ "$TAG_COUNT" -ge 2 ]; then
    check_passed "Found $TAG_COUNT tags (pre-restructure + v1.0.0)"
else
    check_failed "Only found $TAG_COUNT tags (expected ≥2)"
fi

# ============================================================================
# FINAL REPORT
# ============================================================================
section "VALIDATION SUMMARY"

TOTAL=$((PASSED + FAILED))
PERCENTAGE=$((PASSED * 100 / TOTAL))

echo -e "${GREEN}✅ PASSED:${NC} $PASSED"
echo -e "${RED}❌ FAILED:${NC} $FAILED"
echo -e "${BLUE}📊 TOTAL:${NC}  $TOTAL"
echo -e "${YELLOW}📈 SUCCESS RATE: ${PERCENTAGE}%${NC}\n"

if [ "$FAILED" -eq 0 ]; then
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║       🎉 ALL VALIDATIONS PASSED - READY FOR PRODUCTION     ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    exit 0
elif [ "$PERCENTAGE" -ge 90 ]; then
    echo -e "${YELLOW}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║       ⚠️  MOSTLY VALIDATED - REVIEW FAILURES ABOVE        ║${NC}"
    echo -e "${YELLOW}╚════════════════════════════════════════════════════════════╝${NC}"
    exit 1
else
    echo -e "${RED}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║  ❌ VALIDATION FAILED - RESOLVE ISSUES BEFORE DEPLOYMENT   ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════════════════════════╝${NC}"
    exit 2
fi
