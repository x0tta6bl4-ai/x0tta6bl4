#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUTPUT_ROOT="${OUTPUT_ROOT:-$ROOT_DIR/.tmp/micro_niche_scout}"
PID_FILE="$OUTPUT_ROOT/micro_niche_scout.pid"
RUN_LOG="$OUTPUT_ROOT/daemon.out"

mkdir -p "$OUTPUT_ROOT"

if [[ -f "$PID_FILE" ]]; then
  existing_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "${existing_pid}" ]] && kill -0 "$existing_pid" 2>/dev/null; then
    echo "micro_niche_scout already running: pid=$existing_pid"
    exit 0
  fi
fi

INTERVAL_SEC="${INTERVAL_SEC:-2700}"
MAX_RESULTS="${MAX_RESULTS:-3}"
TIMEOUT_SEC="${TIMEOUT_SEC:-8}"
QUERIES_PER_BUCKET="${QUERIES_PER_BUCKET:-2}"

nohup python3 "$ROOT_DIR/scripts/agents/micro_niche_scout.py" \
  --daemon \
  --interval-sec "$INTERVAL_SEC" \
  --max-results "$MAX_RESULTS" \
  --timeout-sec "$TIMEOUT_SEC" \
  --queries-per-bucket "$QUERIES_PER_BUCKET" \
  --bucket telegram_ops \
  --bucket vpn_runtime \
  --bucket release_hardening \
  --bucket fiveg_edge \
  --bucket agent_coordination \
  --output-root "$OUTPUT_ROOT" \
  </dev/null >>"$RUN_LOG" 2>&1 &

new_pid="$!"
sleep 1

if ! kill -0 "$new_pid" 2>/dev/null; then
  echo "micro_niche_scout failed to stay running; inspect $RUN_LOG"
  exit 1
fi

if [[ ! -f "$PID_FILE" ]]; then
  echo "$new_pid" > "$PID_FILE"
fi

echo "micro_niche_scout started: pid=$new_pid"
echo "output_root=$OUTPUT_ROOT"
echo "tail -f $RUN_LOG"
