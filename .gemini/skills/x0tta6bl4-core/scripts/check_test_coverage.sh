#!/bin/bash
set -euo pipefail

echo "Running test coverage check..."
pytest --cov=src --cov-report=term-missing --cov-fail-under=75
echo "Test coverage check completed successfully."
