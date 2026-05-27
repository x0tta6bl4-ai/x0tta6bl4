#!/usr/bin/env bash
set -euo pipefail

STATE_FILE="${STATE_FILE:-/opt/x0tta6bl4-mesh/state/runtime-state.json}"

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required" >&2
  exit 2
fi

if [ ! -f "$STATE_FILE" ]; then
  echo "runtime-state missing: $STATE_FILE"
  exit 1
fi

jq -r '
  [
    "mode=" + (.mode // "unknown"),
    "action=" + (.recommended_action // "observe"),
    "reason=" + (.reason // "-"),
    "listener_443_ok=" + ((.probes.listener_443_ok // false) | tostring),
    "xui_service_ok=" + ((.probes.xui_service_ok // false) | tostring),
    "transport_status=" + (.transport_summary.status // "unknown"),
    "telegram_media_status=" + (.transport_summary.telegram_media_status // "unknown")
  ] | join(" ")
' "$STATE_FILE"
