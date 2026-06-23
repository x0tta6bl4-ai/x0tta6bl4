#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUTPUT_ROOT="${OUTPUT_ROOT:-$ROOT_DIR/.tmp/micro_niche_scout}"
PID_FILE="$OUTPUT_ROOT/micro_niche_scout.pid"

if [[ ! -f "$PID_FILE" ]]; then
  echo "micro_niche_scout is not running (pid file missing)"
  exit 0
fi

pid="$(cat "$PID_FILE" 2>/dev/null || true)"
if [[ -z "$pid" ]]; then
  rm -f "$PID_FILE"
  echo "micro_niche_scout pid file was empty and has been cleared"
  exit 0
fi

if kill -0 "$pid" 2>/dev/null; then
  kill "$pid"
  echo "micro_niche_scout stopped: pid=$pid"
else
  echo "micro_niche_scout process not found: pid=$pid"
fi

rm -f "$PID_FILE"
