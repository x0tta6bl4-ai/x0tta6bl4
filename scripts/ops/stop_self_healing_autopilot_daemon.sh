#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

PID_FILE=".tmp/self_healing/autopilot_daemon.pid"

if [[ ! -f "$PID_FILE" ]]; then
  printf '{"status":"not_running","reason":"no_pid_file"}\n'
  exit 0
fi

PID="$(cat "$PID_FILE" 2>/dev/null || true)"
if [[ "$PID" =~ ^[0-9]+$ ]] && kill -0 "$PID" 2>/dev/null; then
  kill "$PID" || true
  rm -f "$PID_FILE"
  printf '{"status":"stopped","pid":%s}\n' "$PID"
else
  rm -f "$PID_FILE"
  printf '{"status":"not_running","reason":"stale_pid"}\n'
fi
