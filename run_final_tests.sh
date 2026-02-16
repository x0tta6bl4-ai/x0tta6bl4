#!/bin/bash
# Final test execution and report generation for WEST-0104

set -e

export PYTHONFAULTHANDLER=1

PYTEST_TIMEOUT="${PYTEST_TIMEOUT:-25m}"

echo "========================================"
echo "WEST-0104: Unit Tests + CI/CD"
echo "Final Validation & Report"
echo "========================================"
echo ""

# Run all tests
echo "[1/3] Running all charter tests..."
timeout "$PYTEST_TIMEOUT" python -m pytest tests/test_charter_*.py -v --tb=short --cov=src/westworld --cov-report=term-missing 2>&1 | tee test_results.txt

echo ""
echo "[2/3] Generating coverage HTML report..."
timeout "$PYTEST_TIMEOUT" python -m pytest tests/test_charter_*.py --cov=src/westworld --cov-report=html

echo ""
echo "[3/3] Summary statistics..."
python -c "
import pathlib
import json

# Count test files
test_files = list(pathlib.Path('tests').glob('test_charter_*.py'))
print(f'Test Files Created: {len(test_files)}')

# Count tests in each file
total_tests = 0
for test_file in sorted(test_files):
    content = test_file.read_text()
    test_count = content.count('def test_')
    print(f'  - {test_file.name}: {test_count} tests')
    total_tests += test_count

print(f'Total Test Cases: {total_tests}')
print(f'Coverage Report: htmlcov/index.html')
"

echo ""
echo "========================================"
echo "✅ WEST-0104 TEST EXECUTION COMPLETE"
echo "========================================"
