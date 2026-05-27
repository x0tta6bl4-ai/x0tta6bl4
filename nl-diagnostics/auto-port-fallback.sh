#!/bin/bash
# Автоматический фоллбэк портов при высоком уровне сбросов

set -euo pipefail

STATE_DIR="/var/lib/x0tta6bl4-audit"
LOG_FILE="/var/log/x0tta6bl4_audit.log"
LOCK_FILE="${STATE_DIR}/auto-port-fallback.lock"
STAMP_FILE="${STATE_DIR}/auto-port-fallback.restart.stamp"
COOLDOWN_SEC=1800
MAX_LOAD_PER_CPU=4

log() {
    printf '[%s] auto-port-fallback: %s\n' "$(date -Is)" "$*" >> "$LOG_FILE"
}

mkdir -p "$STATE_DIR"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    log "skip: already running"
    exit 0
fi

read -r LOAD_1M _ < /proc/loadavg
CPU_COUNT=$(nproc 2>/dev/null || echo 1)
if awk -v load="$LOAD_1M" -v cpus="$CPU_COUNT" -v max="$MAX_LOAD_PER_CPU" 'BEGIN { exit !(load > cpus * max) }'; then
    log "skip: host overloaded load_1m=${LOAD_1M} limit=$((CPU_COUNT * MAX_LOAD_PER_CPU))"
    exit 0
fi

if [ -e "$STAMP_FILE" ]; then
    NOW=$(date +%s)
    LAST_RESTART=$(stat -c %Y "$STAMP_FILE" 2>/dev/null || echo 0)
    if (( NOW - LAST_RESTART < COOLDOWN_SEC )); then
        log "skip: restart cooldown active cooldown_left_sec=$((COOLDOWN_SEC - (NOW - LAST_RESTART)))"
        exit 0
    fi
fi

RST_COUNT=$(ss -Hti 2>/dev/null | grep -c 'rst_recv' || true)
if [ "$RST_COUNT" -gt 20 ]; then
    log "high tcp resets rst_count=${RST_COUNT}; switching default port to 8443"
    touch "$STAMP_FILE"
    sqlite3 -busy-timeout 5000 /etc/x-ui/x-ui.db "UPDATE settings SET value = '8443' WHERE key = 'default_port';"
    systemctl restart x-ui.service
    log "x-ui restarted after default port fallback"
fi
