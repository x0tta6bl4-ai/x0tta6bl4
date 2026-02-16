#!/usr/bin/env bash
set -euo pipefail

PYTEST_BIN="${PYTEST_BIN:-/mnt/projects/.venv/bin/pytest}"
if [[ ! -x "${PYTEST_BIN}" ]]; then
  PYTEST_BIN="$(command -v pytest)"
fi

COVERAGE_THRESHOLD="${COVERAGE_THRESHOLD:-65}"

echo "Running test coverage check..."
# Keep this gate focused on critical runtime paths to stay deterministic in CI.
PYTEST_ADDOPTS="" "${PYTEST_BIN}" \
  -o addopts="" \
  tests/unit/core tests/unit/api tests/unit/security \
  --tb=short -q \
  --cov=src/core --cov=src/api --cov=src/security \
  --cov-report=term-missing \
  --cov-report=xml:coverage.xml \
  --cov-fail-under="${COVERAGE_THRESHOLD}" || {
  echo "Test coverage check failed. Ensure coverage is at least ${COVERAGE_THRESHOLD}%."
  exit 1
}
echo "Test coverage check completed successfully."
