#!/bin/bash
# Run accessibility audit for x0tta6bl4
# Tests WCAG 2.1 compliance

set -e

echo "🔍 Running WCAG 2.1 Accessibility Audit..."

# Run accessibility tests
python3 -m pytest tests/accessibility/test_wcag_compliance.py -v

# Check for common accessibility issues
echo "✅ Accessibility audit complete"

