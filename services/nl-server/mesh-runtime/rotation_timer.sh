#!/bin/bash
set -euo pipefail

LOG_FILE="/opt/x0tta6bl4-mesh/logs/rotation.log"
ROTATION_FILE="/opt/x0tta6bl4-mesh/configs/rotation_metadata.json"

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG_FILE"
}

need_rotation() {
  if [ ! -f "$ROTATION_FILE" ]; then
    return 0
  fi

  local last_rotation last_epoch now_epoch hours_diff
  last_rotation=$(jq -r '.last_rotation // empty' "$ROTATION_FILE" 2>/dev/null || true)
  if [ -z "$last_rotation" ]; then
    return 0
  fi

  last_epoch=$(date -d "$last_rotation" +%s 2>/dev/null || true)
  now_epoch=$(date +%s)
  if [ -z "$last_epoch" ]; then
    return 0
  fi
  hours_diff=$(( (now_epoch - last_epoch) / 3600 ))
  if [ "$hours_diff" -lt 24 ]; then
    log "Ротация не требуется (прошло $hours_diff часов)"
    return 1
  fi
  return 0
}

reload_xray() {
  pkill -USR1 -f 'xray-linux-amd64.real -c bin/config.json' 2>/dev/null || true
}

wait_for_443_local() {
  local i
  for i in $(seq 1 20); do
    if ss -ltnp | awk '$1 == "LISTEN" && $4 ~ /:443$/ { found=1 } END { exit(found ? 0 : 1) }'; then
      return 0
    fi
    sleep 1
  done
  return 1
}

if ! need_rotation; then
  exit 0
fi

log "Начало безопасной ротации параметров"
python3 /opt/x0tta6bl4-mesh/scripts/full_stealth_config.py >>"$LOG_FILE" 2>&1
reload_xray

if wait_for_443_local; then
  log "Ротация завершена, xray перечитал конфиг без restart x-ui"
else
  log "ПРЕДУПРЕЖДЕНИЕ: после ротации listener :443 не подтвержден"
  exit 1
fi
