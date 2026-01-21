#!/bin/bash

# Week 1 Validation Script
# Runs security audit and performance baseline

set -euo pipefail

PROJECT_ROOT="/mnt/AC74CC2974CBF3DC"
cd "$PROJECT_ROOT"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                                                              ║"
echo "║     🚀 WEEK 1 VALIDATION - STARTING NOW                     ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Step 1: Security Audit
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 1: Security Audit"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python3 scripts/security_audit_checklist.py
AUDIT_EXIT=$?

if [ $AUDIT_EXIT -ne 0 ]; then
    echo "❌ Security audit failed. Please fix issues before continuing."
    exit 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 2: Performance Baseline"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "⚠️  Note: This requires the server to be running on http://localhost:8080"
echo ""

# Check if server is running
if curl -s http://localhost:8080/health > /dev/null 2>&1; then
    python3 scripts/performance_baseline.py
    BASELINE_EXIT=$?
    
    if [ $BASELINE_EXIT -ne 0 ]; then
        echo "❌ Performance baseline failed."
        exit 1
    fi
else
    echo "⚠️  Server is not running. Skipping performance baseline."
    echo "   To run baseline later:"
    echo "   1. Start server: python -m src.core.app"
    echo "   2. Run: python3 scripts/performance_baseline.py"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ WEEK 1 VALIDATION COMPLETE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Next steps:"
echo "  • Review security audit results"
echo "  • Review performance baseline (if completed)"
echo "  • Proceed to staging deployment (Jan 1-2)"
echo ""

