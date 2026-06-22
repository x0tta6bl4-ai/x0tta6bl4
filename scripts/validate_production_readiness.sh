#!/bin/bash
# Local readiness validation for x0tta6bl4.
# Local checks alone are not production deployment proof.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REAL_READINESS_JSON=".tmp/validation-shards/real-readiness-current.json"
REAL_READINESS_MD=".tmp/validation-shards/real-readiness-current.md"
cd "$ROOT_DIR"

echo "🔍 Validating local readiness checks..."

ERRORS=0
WARNINGS=0

# 1. Health checks
echo "📋 Checking health endpoints..."
if python3 -m pytest tests/unit/test_health.py -v --tb=no -q 2>&1 | grep -q "PASSED"; then
    echo "✅ Health endpoint tests passing"
else
    echo "❌ Health endpoint tests failing"
    ((ERRORS+=1))
fi

# 2. Accessibility compliance
echo "📋 Checking accessibility compliance..."
if python3 -m pytest tests/accessibility/test_wcag_compliance.py -v --tb=no -q 2>&1 | grep -q "PASSED"; then
    echo "✅ Accessibility tests passing"
else
    echo "⚠️  Accessibility tests failing"
    ((WARNINGS+=1))
fi

# 3. Stress tests
echo "📋 Checking stress tests..."
if python3 -m pytest tests/chaos/test_anti_censorship.py -v --tb=no -q 2>&1 | grep -q "PASSED"; then
    echo "✅ Stress tests passing"
else
    echo "⚠️  Stress tests failing"
    ((WARNINGS+=1))
fi

# 4. Kubernetes manifests
echo "📋 Checking Kubernetes manifests..."
if [ -f "deployment/kubernetes/deployment.yaml" ]; then
    echo "✅ Deployment manifest exists"
else
    echo "❌ Deployment manifest missing"
    ((ERRORS+=1))
fi

if [ -f "deployment/kubernetes/service.yaml" ]; then
    echo "✅ Service manifest exists"
else
    echo "❌ Service manifest missing"
    ((ERRORS+=1))
fi

# 5. Health checks in deployment
if grep -q "livenessProbe" deployment/kubernetes/deployment.yaml && \
   grep -q "readinessProbe" deployment/kubernetes/deployment.yaml; then
    echo "✅ Health checks configured"
else
    echo "❌ Health checks missing"
    ((ERRORS+=1))
fi

# 6. Security checks
if grep -q "x0tta6bl4_PRODUCTION" deployment/kubernetes/deployment.yaml; then
    echo "✅ Production mode configured"
else
    echo "⚠️  Production mode not explicitly set"
    ((WARNINGS+=1))
fi

# 7. Resource limits
if grep -q "resources:" deployment/kubernetes/deployment.yaml; then
    echo "✅ Resource limits configured"
else
    echo "⚠️  Resource limits missing"
    ((WARNINGS+=1))
fi

# 8. Immutable images
if [ -f "scripts/build_immutable_image.sh" ]; then
    echo "✅ Immutable image build script exists"
else
    echo "⚠️  Immutable image script missing"
    ((WARNINGS+=1))
fi

# Summary
echo ""
echo "📊 Validation Summary:"
echo "   Errors: $ERRORS"
echo "   Warnings: $WARNINGS"

if [ "$ERRORS" -eq 0 ]; then
    echo "✅ Local readiness checks passed"
    echo "Local checks are not production deployment proof."
    echo "Running fail-closed real-readiness gate..."
    if python3 "$ROOT_DIR/scripts/ops/check_real_readiness.py" \
        --write-json "$REAL_READINESS_JSON" \
        --write-md "$REAL_READINESS_MD" >/dev/null; then
        echo "✅ REAL READINESS GATE: PASSED"
        echo "This gate result still does not prove live customer traffic, external DPI bypass,"
        echo "payment settlement finality, or production SLOs without separate evidence."
    else
        echo "❌ REAL READINESS GATE: BLOCKED"
        echo "Local readiness checks passed, but production deployment is not allowed yet."
        echo "Report: $REAL_READINESS_JSON"
        exit 1
    fi
    exit 0
else
    echo "❌ Local readiness checks failed"
    exit 1
fi
