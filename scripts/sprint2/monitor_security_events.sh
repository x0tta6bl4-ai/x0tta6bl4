#!/bin/bash
# scripts/sprint2/monitor_security_events.sh
set -euo pipefail

log() { echo "[$(date -Iseconds)] $*"; }

log "=== Monitoring Falco Security Events (tail) ==="
kubectl logs -n falco-system -l app=falco -f --tail=100 | while read -r line; do
  if echo "$line" | grep -q "priority=Critical"; then
    echo -e "\033[1;31m[CRITICAL] $line\033[0m"
  elif echo "$line" | grep -q "priority=Warning"; then
    echo -e "\033[1;33m[WARNING] $line\033[0m"
  else
    echo "$line"
  fi
done
