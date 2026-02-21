#!/usr/bin/env bash
set -euo pipefail

TARGET_INPUT="${1:-libx0t/network/obfuscation}"
TEST_PATH="${2:-tests/unit/network/obfuscation}"
MIN_COVERAGE="${3:-80}"

# Accept either filesystem-style path (libx0t/network/foo.py) or dotted module path.
TARGET_MODULE="${TARGET_INPUT#./}"
TARGET_MODULE="${TARGET_MODULE%/}"
TARGET_MODULE="${TARGET_MODULE%.py}"
TARGET_MODULE="${TARGET_MODULE//\//.}"

pytest "$TEST_PATH" \
  -o addopts='' \
  --cov="$TARGET_MODULE" \
  --cov-report=term-missing \
  --cov-fail-under="$MIN_COVERAGE"
