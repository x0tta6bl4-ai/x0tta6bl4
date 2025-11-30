#!/bin/bash
# Production Readiness Check for x0tta6bl4 v3.0.0
set -e

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║       x0tta6bl4 Production Readiness Check                   ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

PASS=0
FAIL=0
WARN=0

check() {
    local name="$1"
    local status="$2"
    local msg="$3"
    
    if [ "$status" = "pass" ]; then
        echo "   ✅ $name: $msg"
        ((PASS++))
    elif [ "$status" = "fail" ]; then
        echo "   ❌ $name: $msg"
        ((FAIL++))
    else
        echo "   ⚠️  $name: $msg"
        ((WARN++))
    fi
}

# 1. Git Repository
echo "1️⃣  Git Repository:"
if [ -z "$(git status --porcelain 2>/dev/null)" ]; then
    check "Status" "pass" "All files committed"
else
    UNCOMMITTED=$(git status --porcelain | wc -l)
    check "Status" "fail" "$UNCOMMITTED uncommitted files"
fi

TAG=$(git describe --tags --exact-match HEAD 2>/dev/null || echo "")
if [ -n "$TAG" ]; then
    check "Tag" "pass" "$TAG"
else
    check "Tag" "warn" "No release tag on HEAD"
fi

# 2. Core Files
echo ""
echo "2️⃣  Core Files:"
[ -f "src/core/app.py" ] && check "FastAPI App" "pass" "exists" || check "FastAPI App" "fail" "missing"
[ -f "src/mesh/slot_sync.py" ] && check "Mesh Sync" "pass" "exists" || check "Mesh Sync" "fail" "missing"
[ -f "src/ml/graphsage_anomaly_detector.py" ] && check "GraphSAGE AI" "pass" "exists" || check "GraphSAGE AI" "fail" "missing"
[ -f "src/dao/governance.py" ] && check "DAO Governance" "pass" "exists" || check "DAO Governance" "fail" "missing"
[ -f "src/security/post_quantum.py" ] && check "PQ Crypto" "pass" "exists" || check "PQ Crypto" "fail" "missing"

# 3. Helm Chart
echo ""
echo "3️⃣  Helm Chart:"
if [ -f "helm/x0tta6bl4/Chart.yaml" ]; then
    check "Chart.yaml" "pass" "exists"
    VERSION=$(grep "^version:" helm/x0tta6bl4/Chart.yaml | awk '{print $2}')
    check "Version" "pass" "$VERSION"
    
    if helm lint helm/x0tta6bl4/ > /dev/null 2>&1; then
        check "Lint" "pass" "valid"
    else
        check "Lint" "warn" "has warnings"
    fi
else
    check "Chart.yaml" "fail" "missing"
fi

# 4. Docker
echo ""
echo "4️⃣  Docker:"
[ -f "Dockerfile" ] && check "Dockerfile" "pass" "exists" || check "Dockerfile" "fail" "missing"
[ -f ".dockerignore" ] && check ".dockerignore" "pass" "exists" || check ".dockerignore" "warn" "missing"

# 5. Testing
echo ""
echo "5️⃣  Testing:"
[ -d "tests/k6" ] && check "k6 Load Tests" "pass" "exists" || check "k6 Load Tests" "fail" "missing"
[ -f "scripts/chaos-pod-kill.sh" ] && check "Chaos Tests" "pass" "exists" || check "Chaos Tests" "warn" "missing"
[ -d "results" ] && check "Test Results" "pass" "exists" || check "Test Results" "warn" "missing"

# 6. Documentation
echo ""
echo "6️⃣  Documentation:"
[ -f "README.md" ] && check "README" "pass" "exists" || check "README" "fail" "missing"
[ -f "CONTRIBUTING.md" ] && check "CONTRIBUTING" "pass" "exists" || check "CONTRIBUTING" "warn" "missing"
[ -f "LICENSE" ] && check "LICENSE" "pass" "exists" || check "LICENSE" "warn" "missing"

# 7. CI/CD
echo ""
echo "7️⃣  CI/CD:"
[ -f ".github/workflows/ci.yaml" ] && check "CI Pipeline" "pass" "exists" || check "CI Pipeline" "warn" "missing"
[ -f ".github/workflows/deploy-eks.yaml" ] && check "Deploy Pipeline" "pass" "exists" || check "Deploy Pipeline" "warn" "missing"

# Summary
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📊 SUMMARY:"
echo "   ✅ Passed: $PASS"
echo "   ❌ Failed: $FAIL"
echo "   ⚠️  Warnings: $WARN"
echo ""

TOTAL=$((PASS + FAIL + WARN))
SCORE=$((PASS * 100 / TOTAL))

echo "   Production Readiness Score: ${SCORE}%"
echo ""

if [ $FAIL -eq 0 ]; then
    echo "   🚀 STATUS: READY FOR PRODUCTION"
else
    echo "   🔧 STATUS: FIX $FAIL ISSUES BEFORE PRODUCTION"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

exit $FAIL
