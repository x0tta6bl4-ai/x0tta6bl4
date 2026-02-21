#!/bin/bash
set -euo pipefail

echo "Running pip-audit..."
pip-audit --local

echo "Running bandit..."
bandit -r src/ -ll

echo "Running safety scan..."
if safety scan --help >/dev/null 2>&1; then
  safety scan
else
  # Backward compatibility for older Safety versions.
  safety check
fi

echo "Security checks completed successfully."
