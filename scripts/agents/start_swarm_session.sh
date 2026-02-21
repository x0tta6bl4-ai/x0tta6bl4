#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <agent-key>" >&2
  exit 2
fi

AGENT="$1"
ROOT="$(git rev-parse --show-toplevel)"
GIT_COMMON_RAW="$(git rev-parse --git-common-dir)"
GIT_DIR="$(git rev-parse --git-dir)"
if [[ "$GIT_COMMON_RAW" = /* ]]; then
  GIT_COMMON="$GIT_COMMON_RAW"
else
  GIT_COMMON="$ROOT/$GIT_COMMON_RAW"
fi
SWARM_DIR="$GIT_COMMON/swarm"
PID_FILE="$SWARM_DIR/${AGENT}.watch.pid"
LOG_FILE="$SWARM_DIR/${AGENT}.watch.log"

TTL="${SWARM_LEASE_TTL:-1800}"
INTERVAL="${SWARM_HEARTBEAT_INTERVAL:-300}"

mkdir -p "$SWARM_DIR"
export SWARM_AGENT="$AGENT"
printf "%s\n" "$AGENT" > "$GIT_DIR/swarm_agent"

"$ROOT/scripts/agents/install_swarm_hook.sh" >/dev/null
"$ROOT/scripts/agents/swarm_coord.py" claim-owned --agent "$AGENT" --ttl "$TTL" --note "session-start"

if [[ "${SWARM_NO_DAEMON:-0}" = "1" ]]; then
  echo "[swarm] session initialized for '$AGENT' without daemon."
  exit 0
fi

if [[ -f "$PID_FILE" ]]; then
  OLD_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "$OLD_PID" ]] && kill -0 "$OLD_PID" 2>/dev/null; then
    echo "[swarm] heartbeat daemon already running for '$AGENT' (pid=$OLD_PID)."
    exit 0
  fi
fi

nohup "$ROOT/scripts/agents/swarm_coord.py" watch \
  --agent "$AGENT" \
  --ttl "$TTL" \
  --interval "$INTERVAL" \
  >"$LOG_FILE" 2>&1 &
PID="$!"
echo "$PID" > "$PID_FILE"

echo "[swarm] session started for '$AGENT' (pid=$PID, ttl=$TTL, interval=$INTERVAL)."
echo "[swarm] log: $LOG_FILE"
