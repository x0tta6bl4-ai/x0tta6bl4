#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

PID_FILE=".tmp/self_healing/autopilot_daemon.pid"
LOG_FILE=".tmp/self_healing/autopilot_daemon.log"
mkdir -p "$(dirname "$PID_FILE")"

if [[ -f "$PID_FILE" ]]; then
  PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ "$PID" =~ ^[0-9]+$ ]] && kill -0 "$PID" 2>/dev/null; then
    printf '{"status":"already_running","pid":%s,"log":"%s"}\n' "$PID" "$LOG_FILE"
    exit 0
  fi
fi

setsid python3 -u scripts/ops/run_self_healing_autopilot_cycle.py \
  --cycles 0 \
  --interval-seconds 120 \
  --output .tmp/self_healing/autopilot_status_latest.json \
  --history-jsonl .tmp/self_healing/autopilot_history.jsonl \
  >>"$LOG_FILE" 2>&1 < /dev/null &

PID="$!"
printf '%s\n' "$PID" > "$PID_FILE"
printf '{"status":"started","pid":%s,"log":"%s","pid_file":"%s"}\n' "$PID" "$LOG_FILE" "$PID_FILE"
