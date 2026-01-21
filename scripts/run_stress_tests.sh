#!/bin/bash
# Run anti-censorship stress tests for x0tta6bl4

set -e

echo "🔥 Running Anti-Censorship Stress Tests..."

# Run stress tests
python3 -m pytest tests/chaos/test_anti_censorship.py -v

# Run with more verbose output
echo "✅ Stress tests complete"

