#!/bin/bash
set -euo pipefail

STATE_DIR="/opt/x0tta6bl4-mesh/state"
STATE_FILE="$STATE_DIR/runtime-state.json"
COOLDOWN_FILE="$STATE_DIR/restart-cooldown.json"
LOG_PREFIX="[$(date +%Y-%m-%d\ %H:%M:%S)]"
RESTART_COOLDOWN_SEC=600
mkdir -p "$STATE_DIR"

python3 /opt/x0tta6bl4-mesh/scripts/build_runtime_state.py >/dev/null 2>&1 || true

if [ ! -f "$STATE_FILE" ]; then
  echo "$LOG_PREFIX runtime-state missing"
  exit 0
fi

mode=$(jq -r '.mode // "unknown"' "$STATE_FILE")
action=$(jq -r '.recommended_action // "observe"' "$STATE_FILE")
reason=$(jq -r '.reason // "-"' "$STATE_FILE")
listener_ok=$(jq -r '.probes.listener_443_ok // false' "$STATE_FILE")
xui_ok=$(jq -r '.probes.xui_service_ok // false' "$STATE_FILE")
failed_secondary=$(jq -r '.probes.secondary_listener_failures // [] | join(",")' "$STATE_FILE")

if [ -n "$failed_secondary" ]; then
  echo "$LOG_PREFIX mode=$mode action=$action reason=$reason secondary_failures=$failed_secondary"
else
  echo "$LOG_PREFIX mode=$mode action=$action reason=$reason"
fi

should_restart=0
if [ "$action" = "restart_primary" ] && { [ "$listener_ok" != "true" ] || [ "$xui_ok" != "true" ]; }; then
  should_restart=1
fi

if [ "$should_restart" -ne 1 ]; then
  exit 0
fi

now=$(date +%s)
last_restart=0
if [ -f "$COOLDOWN_FILE" ]; then
  last_restart=$(jq -r '.last_restart_epoch // 0' "$COOLDOWN_FILE" 2>/dev/null || echo 0)
fi

if [ $((now - last_restart)) -lt "$RESTART_COOLDOWN_SEC" ]; then
  echo "$LOG_PREFIX restart skipped by cooldown"
  exit 0
fi

echo "$LOG_PREFIX controlled restart of x-ui"
systemctl restart x-ui
sleep 5
python3 /opt/x0tta6bl4-mesh/scripts/build_runtime_state.py >/dev/null 2>&1 || true
printf '{"last_restart_epoch": %s, "last_restart_reason": %s}\n' "$now" "$(jq -Rs . <<<"$reason")" | jq . > "$COOLDOWN_FILE"
