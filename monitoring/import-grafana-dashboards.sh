#!/usr/bin/env bash
# Import Grafana dashboards via HTTP API.
# Usage: ./import-grafana-dashboards.sh [grafana-url] [admin-pass]
set -euo pipefail
GRAFANA_URL=${1:-http://localhost:3000}
ADMIN_PASS=${2:-admin}
DASH_DIR="monitoring/dashboards"
[ -d "$DASH_DIR" ] || { echo "Dashboard dir $DASH_DIR not found" >&2; exit 1; }
for FILE in $DASH_DIR/*.json; do
  echo "Importing $FILE" >&2
  PAYLOAD=$(jq -c '{dashboard: ., overwrite: true}' "$FILE")
  curl -s -u admin:"$ADMIN_PASS" -H 'Content-Type: application/json' -X POST "$GRAFANA_URL/api/dashboards/db" -d "$PAYLOAD" | jq '.status,.slug' || true
done
echo "Done."
