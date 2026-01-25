#!/usr/bin/env bash
# Collect baseline latency between local host and mesh node list.
# Usage: ./latency-baseline.sh nodes.txt
set -euo pipefail
FILE=${1:-nodes.txt}
[ -f "$FILE" ] || { echo "Nodes file $FILE not found" >&2; exit 1; }
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
OUT="latency-baseline-$TS.csv"
echo "node,avg_ms,min_ms,max_ms,loss_percent" > "$OUT"
while read -r NODE; do
  [ -z "$NODE" ] && continue
  echo "Probing $NODE" >&2
  # Using 5 ICMP echo requests
  PING=$(ping -c 5 -q "$NODE" || true)
  AVG=$(echo "$PING" | awk -F'/' '/rtt/ {print $5}')
  MIN=$(echo "$PING" | awk -F'/' '/rtt/ {print $4}')
  MAX=$(echo "$PING" | awk -F'/' '/rtt/ {print $6}' | awk '{print $1}')
  LOSS=$(echo "$PING" | awk -F',' '/packet loss/ {print $3}' | tr -dc '0-9.' )
  echo "$NODE,$AVG,$MIN,$MAX,$LOSS" >> "$OUT"
done < "$FILE"
echo "Saved baseline to $OUT" >&2
