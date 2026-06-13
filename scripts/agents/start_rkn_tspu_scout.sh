#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUTPUT_ROOT="${OUTPUT_ROOT:-$ROOT_DIR/.tmp/rkn_tspu_scout}"
mkdir -p "$OUTPUT_ROOT"

INTERVAL_SEC="${INTERVAL_SEC:-2700}"
MAX_RESULTS="${MAX_RESULTS:-3}"
TIMEOUT_SEC="${TIMEOUT_SEC:-8}"
QUERIES_PER_BUCKET="${QUERIES_PER_BUCKET:-2}"

echo "Use a persistent PTY/session for reliable launch in this environment."
echo "Command:"
echo "python3 $ROOT_DIR/scripts/agents/rkn_tspu_scout.py --daemon --interval-sec $INTERVAL_SEC --max-results $MAX_RESULTS --timeout-sec $TIMEOUT_SEC --queries-per-bucket $QUERIES_PER_BUCKET --bucket rkn_actions --bucket tspu_operators --bucket anti_censorship --bucket regulation --bucket field_reports --output-root $OUTPUT_ROOT"
