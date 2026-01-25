#!/bin/bash

# Staging Deployment + Load Test Script
# Runs complete staging validation

set -euo pipefail

PROJECT_ROOT="/mnt/AC74CC2974CBF3DC"
cd "$PROJECT_ROOT"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                                                              ║"
echo "║     🚀 STAGING DEPLOYMENT + LOAD TEST                        ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Step 1: Staging Deployment
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 1: Staging Deployment"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python3 scripts/staging_deployment.py
DEPLOY_EXIT=$?

if [ $DEPLOY_EXIT -ne 0 ]; then
    echo "❌ Staging deployment failed. Please fix issues before continuing."
    exit 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 2: Production Load Test"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "⚠️  Note: This will run for ~5 minutes"
echo ""

python3 scripts/run_load_test.py
LOAD_TEST_EXIT=$?

if [ $LOAD_TEST_EXIT -ne 0 ]; then
    echo "❌ Load test failed."
    exit 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 3: Extended Chaos Testing (Optional)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "⚠️  Note: This is optional but recommended"
echo ""

read -p "Run chaos tests? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    python3 tests/chaos/staging_chaos_test.py
    CHAOS_EXIT=$?
    
    if [ $CHAOS_EXIT -ne 0 ]; then
        echo "⚠️  Chaos tests had issues (non-critical)"
    fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ STAGING VALIDATION COMPLETE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Next steps:"
echo "  • Review load test results"
echo "  • Review chaos test results (if run)"
echo "  • Proceed to team training (Jan 3)"
echo ""

