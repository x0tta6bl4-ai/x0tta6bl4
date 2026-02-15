#!/bin/bash
echo "Running test coverage check..."
pytest --cov=src --cov-fail-under=75 || { echo "Test coverage check failed. Ensure coverage is at least 75%."; exit 1; }
echo "Test coverage check completed successfully."
