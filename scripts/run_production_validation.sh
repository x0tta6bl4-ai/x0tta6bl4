#!/bin/bash
# Local production-claim preflight for x0tta6bl4.
# This runs local checks, but it is not production readiness proof.

set -e

echo "🔍 Running local production-claim preflight..."
echo "Claim boundary: this suite runs local checks and delegates readiness to the"
echo "fail-closed real-readiness gate; it does not prove live customer traffic,"
echo "external DPI bypass, settlement finality, production SLOs, or production readiness."
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
echo "✅ Local production-claim preflight complete"
echo "Production readiness still requires a passing real-readiness gate and separate"
echo "current evidence for live traffic, DPI, settlement, and SLO claims."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
