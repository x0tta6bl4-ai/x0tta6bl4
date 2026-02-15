#!/bin/bash
echo "Running pip-audit..."
pip-audit --local || { echo "pip-audit failed"; exit 1; }

echo "Running bandit..."
bandit -r src/ -ll || { echo "bandit failed"; exit 1; }

echo "Running safety check..."
safety check || { echo "safety check failed"; exit 1; }

echo "Security checks completed successfully."
