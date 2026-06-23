#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUTPUT_ROOT="${OUTPUT_ROOT:-$ROOT_DIR/.tmp/rkn_tspu_scout}"
PID_FILE="$OUTPUT_ROOT/rkn_tspu_scout.pid"

if [[ ! -f "$PID_FILE" ]]; then
  echo "rkn_tspu_scout is not running (pid file missing)"
  exit 0
fi

pid="$(cat "$PID_FILE" 2>/dev/null || true)"
if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
  kill "$pid"
  echo "rkn_tspu_scout stopped: pid=$pid"
else
  echo "rkn_tspu_scout process not found: pid=${pid:-unknown}"
fi

rm -f "$PID_FILE"
