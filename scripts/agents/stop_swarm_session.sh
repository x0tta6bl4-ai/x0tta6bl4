#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <agent-key>" >&2
  exit 2
fi

AGENT="$1"
ROOT="$(git rev-parse --show-toplevel)"
GIT_COMMON_RAW="$(git rev-parse --git-common-dir)"
if [[ "$GIT_COMMON_RAW" = /* ]]; then
  GIT_COMMON="$GIT_COMMON_RAW"
else
  GIT_COMMON="$ROOT/$GIT_COMMON_RAW"
fi
SWARM_DIR="$GIT_COMMON/swarm"
PID_FILE="$SWARM_DIR/${AGENT}.watch.pid"

if [[ -f "$PID_FILE" ]]; then
  PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "$PID" ]] && kill -0 "$PID" 2>/dev/null; then
    kill "$PID" || true
    sleep 1
    if kill -0 "$PID" 2>/dev/null; then
      kill -9 "$PID" || true
    fi
    echo "[swarm] stopped heartbeat daemon for '$AGENT' (pid=$PID)."
  fi
  rm -f "$PID_FILE"
fi

"$ROOT/scripts/agents/swarm_coord.py" release --agent "$AGENT"
echo "[swarm] session closed for '$AGENT'."
