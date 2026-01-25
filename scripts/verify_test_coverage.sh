#!/bin/bash
# Script to verify test coverage for x0tta6bl4
# Usage: ./scripts/verify_test_coverage.sh

set -e

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     Test Coverage Verification Script                        ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check if pytest is available
if ! command -v pytest &> /dev/null; then
    echo "⚠️  pytest not found. Installing..."
    pip install pytest pytest-cov pytest-asyncio
fi

# Check if pytest-cov is available
if ! python3 -c "import pytest_cov" 2>/dev/null; then
    echo "⚠️  pytest-cov not found. Installing..."
    pip install pytest-cov
fi

echo "📊 Running tests with coverage..."
echo ""

# Run tests with coverage
pytest \
    --cov=src \
    --cov-report=html \
    --cov-report=term \
    --cov-report=json \
    --cov-fail-under=90 \
    -v

# Check if coverage report was generated
if [ -f "coverage.json" ]; then
    echo ""
    echo "✅ Coverage report generated:"
    echo "   - HTML: htmlcov/index.html"
    echo "   - JSON: coverage.json"
    echo "   - Terminal: See above"
    
    # Extract coverage percentage from JSON
    if command -v jq &> /dev/null; then
        COVERAGE=$(python3 -c "import json; data = json.load(open('coverage.json')); print(f\"{data['totals']['percent_covered']:.2f}%\")")
        echo ""
        echo "📈 Total Coverage: $COVERAGE"
    fi
else
    echo "⚠️  Coverage report not generated"
fi

echo ""
echo "✅ Test coverage verification complete!"

