#!/bin/bash
# Production Readiness Validation for x0tta6bl4
# Comprehensive checklist for production deployment

set -e

echo "🔍 Validating Production Readiness..."

ERRORS=0
WARNINGS=0

# 1. Health checks
echo "📋 Checking health endpoints..."
if python3 -m pytest tests/unit/test_health.py -v --tb=no -q 2>&1 | grep -q "PASSED"; then
    echo "✅ Health endpoint tests passing"
else
    echo "❌ Health endpoint tests failing"
    ((ERRORS++))
fi

# 2. Accessibility compliance
echo "📋 Checking accessibility compliance..."
if python3 -m pytest tests/accessibility/test_wcag_compliance.py -v --tb=no -q 2>&1 | grep -q "PASSED"; then
    echo "✅ Accessibility tests passing"
else
    echo "⚠️  Accessibility tests failing"
    ((WARNINGS++))
fi

# 3. Stress tests
echo "📋 Checking stress tests..."
if python3 -m pytest tests/chaos/test_anti_censorship.py -v --tb=no -q 2>&1 | grep -q "PASSED"; then
    echo "✅ Stress tests passing"
else
    echo "⚠️  Stress tests failing"
    ((WARNINGS++))
fi

# 4. Kubernetes manifests
echo "📋 Checking Kubernetes manifests..."
if [ -f "deployment/kubernetes/deployment.yaml" ]; then
    echo "✅ Deployment manifest exists"
else
    echo "❌ Deployment manifest missing"
    ((ERRORS++))
fi

if [ -f "deployment/kubernetes/service.yaml" ]; then
    echo "✅ Service manifest exists"
else
    echo "❌ Service manifest missing"
    ((ERRORS++))
fi

# 5. Health checks in deployment
if grep -q "livenessProbe" deployment/kubernetes/deployment.yaml && \
   grep -q "readinessProbe" deployment/kubernetes/deployment.yaml; then
    echo "✅ Health checks configured"
else
    echo "❌ Health checks missing"
    ((ERRORS++))
fi

# 6. Security checks
if grep -q "X0TTA6BL4_PRODUCTION" deployment/kubernetes/deployment.yaml; then
    echo "✅ Production mode configured"
else
    echo "⚠️  Production mode not explicitly set"
    ((WARNINGS++))
fi

# 7. Resource limits
if grep -q "resources:" deployment/kubernetes/deployment.yaml; then
    echo "✅ Resource limits configured"
else
    echo "⚠️  Resource limits missing"
    ((WARNINGS++))
fi

# 8. Immutable images
if [ -f "scripts/build_immutable_image.sh" ]; then
    echo "✅ Immutable image build script exists"
else
    echo "⚠️  Immutable image script missing"
    ((WARNINGS++))
fi

# Summary
echo ""
echo "📊 Validation Summary:"
echo "   Errors: $ERRORS"
echo "   Warnings: $WARNINGS"

if [ $ERRORS -eq 0 ]; then
    echo "✅ Production readiness validation PASSED"
    exit 0
else
    echo "❌ Production readiness validation FAILED"
    exit 1
fi

