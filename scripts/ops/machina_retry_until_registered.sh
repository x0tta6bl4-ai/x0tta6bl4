#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

max_attempts="${MACHINA_RETRY_MAX_ATTEMPTS:-6}"
sleep_seconds="${MACHINA_RETRY_SLEEP_SECONDS:-600}"

attempt=1
while [ "$attempt" -le "$max_attempts" ]; do
  echo "machina retry attempt ${attempt}/${max_attempts}"
  if PYTHONPATH=. python3 scripts/ops/machina_register_services.py --submit; then
    PYTHONPATH=. python3 scripts/ops/machina_listing_watcher.py
    exit 0
  fi

  registered=$(
    python3 - <<'PY'
import json
try:
    data=json.load(open(".tmp/non-bounty/machina_register_services_status.json"))
except Exception:
    print(0)
else:
    print(int(data.get("registered_or_existing_total") or 0))
PY
  )
  if [ "$registered" -ge 8 ]; then
    PYTHONPATH=. python3 scripts/ops/machina_listing_watcher.py
    exit 0
  fi
  if [ "$attempt" -eq "$max_attempts" ]; then
    break
  fi
  sleep "$sleep_seconds"
  attempt=$((attempt + 1))
done

PYTHONPATH=. python3 scripts/ops/machina_listing_watcher.py || true
exit 1
