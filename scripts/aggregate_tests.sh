#!/bin/bash
TEST_DIRS=("project/tests" "tests/core" "tests/api" "tests/network" "tests/security" "tests/self_healing" "tests/resilience" "tests/storage" "tests/monitoring")
export COVERAGE_FILE=.coverage.aggregated

rm -f .coverage.aggregated

for dir in "${TEST_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        echo "Running tests in $dir..."
        python3 -m pytest "$dir" --cov=src --cov-append --cov-report= --ignore=.worktrees --ignore=.tmp --ignore=node_modules || echo "Some tests failed in $dir"
    fi
done

echo "Final Coverage Report:"
python3 -m coverage report --data-file=.coverage.aggregated
python3 -m coverage html --data-file=.coverage.aggregated -d htmlcov_aggregated
