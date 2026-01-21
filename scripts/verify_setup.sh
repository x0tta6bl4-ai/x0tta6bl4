#!/bin/bash
# Setup verification script
# Verifies all components are properly configured

set -e

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     Setup Verification Script                                ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

ERRORS=0
WARNINGS=0

# Check Python files
echo "🐍 Checking Python files..."
if [ -d "src" ]; then
    PYTHON_FILES=$(find src -name "*.py" | wc -l)
    echo "   ✅ Found $PYTHON_FILES Python files"
else
    echo "   ❌ src/ directory not found"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# Check requirements files
echo "📦 Checking requirements files..."
for req in requirements-core.txt requirements-production.txt requirements-optional.txt; do
    if [ -f "$req" ]; then
        echo "   ✅ $req exists"
    else
        echo "   ❌ $req not found"
        ERRORS=$((ERRORS + 1))
    fi
done
echo ""

# Check Helm chart
echo "☸️  Checking Helm chart..."
if [ -d "helm/x0tta6bl4" ]; then
    if [ -f "helm/x0tta6bl4/Chart.yaml" ]; then
        echo "   ✅ Helm chart found"
    else
        echo "   ❌ Chart.yaml not found"
        ERRORS=$((ERRORS + 1))
    fi
    
    TEMPLATES=$(find helm/x0tta6bl4/templates -name "*.yaml" 2>/dev/null | wc -l)
    echo "   ✅ Found $TEMPLATES Helm templates"
else
    echo "   ❌ Helm chart directory not found"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# Check Terraform
echo "🏗️  Checking Terraform..."
if [ -d "terraform" ]; then
    TF_FILES=$(find terraform -name "*.tf" 2>/dev/null | wc -l)
    if [ "$TF_FILES" -gt 0 ]; then
        echo "   ✅ Found $TF_FILES Terraform files"
    else
        echo "   ⚠️  No Terraform files found"
        WARNINGS=$((WARNINGS + 1))
    fi
else
    echo "   ⚠️  Terraform directory not found (optional)"
    WARNINGS=$((WARNINGS + 1))
fi
echo ""

# Check scripts
echo "📜 Checking scripts..."
if [ -d "scripts" ]; then
    SCRIPTS=$(find scripts -name "*.sh" -executable 2>/dev/null | wc -l)
    echo "   ✅ Found $SCRIPTS executable scripts"
else
    echo "   ⚠️  scripts/ directory not found"
    WARNINGS=$((WARNINGS + 1))
fi
echo ""

# Check documentation
echo "📚 Checking documentation..."
DOCS=0
for doc in INSTALLATION_GUIDE.md README_INSTALLATION.md docs/operations/OPERATIONS_GUIDE.md docs/beta/BETA_TESTING_GUIDE.md; do
    if [ -f "$doc" ]; then
        DOCS=$((DOCS + 1))
    fi
done
echo "   ✅ Found $DOCS key documentation files"
echo ""

# Check health check script
echo "🏥 Checking health check script..."
if [ -f "scripts/check_dependencies.py" ]; then
    echo "   ✅ Health check script found"
else
    echo "   ❌ Health check script not found"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# Check CI/CD
echo "🔄 Checking CI/CD..."
if [ -d ".github/workflows" ]; then
    WORKFLOWS=$(find .github/workflows -name "*.yml" 2>/dev/null | wc -l)
    echo "   ✅ Found $WORKFLOWS GitHub Actions workflows"
else
    echo "   ⚠️  GitHub Actions workflows not found (optional)"
    WARNINGS=$((WARNINGS + 1))
fi
echo ""

# Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Verification Summary:"
echo "   Errors: $ERRORS"
echo "   Warnings: $WARNINGS"
echo ""

if [ $ERRORS -eq 0 ]; then
    echo "✅ Setup verification passed!"
    if [ $WARNINGS -gt 0 ]; then
        echo "   ⚠️  Some optional components are missing (non-critical)"
    fi
    exit 0
else
    echo "❌ Setup verification failed!"
    echo "   Please fix the errors above"
    exit 1
fi

