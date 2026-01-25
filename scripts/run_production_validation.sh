#!/bin/bash
# Complete production validation suite for x0tta6bl4
# Runs all validation tests and checks

set -e

echo "🔍 Running Complete Production Validation Suite..."
echo ""

# 1. Production Readiness
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1️⃣  Production Readiness Validation"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
bash scripts/validate_production_readiness.sh
echo ""

# 2. Kubernetes Deployment
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2️⃣  Kubernetes Deployment Validation"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
bash scripts/validate_kubernetes_deployment.sh
echo ""

# 3. Accessibility Tests
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3️⃣  Accessibility Tests (WCAG 2.1)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python3 -m pytest tests/accessibility/test_wcag_compliance.py -v --tb=short -q
echo ""

# 4. Stress Tests
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4️⃣  Stress Tests (Anti-Censorship)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python3 -m pytest tests/chaos/test_anti_censorship.py -v --tb=short -q
echo ""

# 5. Health Endpoint
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "5️⃣  Health Endpoint Tests"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python3 -m pytest tests/unit/test_health.py -v --tb=short -q
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Production Validation Suite Complete"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

