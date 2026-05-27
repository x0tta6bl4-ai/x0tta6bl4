#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
POLICY_FILE="${POLICY_FILE:-$SCRIPT_DIR/health_action_policy.py}"
STATE_FILE="${STATE_FILE:-/opt/x0tta6bl4-mesh/state/runtime-state.json}"
COOLDOWN_FILE="${COOLDOWN_FILE:-/opt/x0tta6bl4-mesh/state/restart-cooldown.json}"
MUTATION_ALLOWED=false

if [ "${NL_XUI_RESTART_APPROVED:-0}" = "1" ]; then
  MUTATION_ALLOWED=true
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required" >&2
  exit 2
fi

if [ ! -f "$STATE_FILE" ]; then
  echo "runtime-state missing: $STATE_FILE" >&2
  exit 1
fi

now_epoch="$(date +%s)"
last_restart_epoch=0
if [ -f "$COOLDOWN_FILE" ]; then
  last_restart_epoch="$(jq -r '.last_restart_epoch // 0' "$COOLDOWN_FILE" 2>/dev/null || echo 0)"
fi

decision_json="$(
  python3 - "$POLICY_FILE" "$STATE_FILE" "$MUTATION_ALLOWED" "$now_epoch" "$last_restart_epoch" <<'PY'
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

policy_path = Path(sys.argv[1])
state_path = Path(sys.argv[2])
mutation_allowed = sys.argv[3] == "true"
now_epoch = int(sys.argv[4])
last_restart_epoch = int(sys.argv[5])

spec = importlib.util.spec_from_file_location("health_action_policy", policy_path)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)

state = json.loads(state_path.read_text(encoding="utf-8"))
decision = module.decide_xui_restart(
    state,
    mutation_allowed=mutation_allowed,
    now_epoch=now_epoch,
    last_restart_epoch=last_restart_epoch,
)
print(json.dumps(decision.to_dict(), sort_keys=True))
PY
)"

echo "$decision_json" | jq -c .

allowed="$(echo "$decision_json" | jq -r '.allowed')"
decision="$(echo "$decision_json" | jq -r '.decision')"

if [ "$allowed" != "true" ]; then
  exit 0
fi

if [ "${NL_HEAL_EXECUTE:-0}" != "1" ]; then
  echo "dry-run: would execute $decision; set NL_HEAL_EXECUTE=1 only during approved maintenance"
  exit 0
fi

systemctl restart x-ui
mkdir -p "$(dirname -- "$COOLDOWN_FILE")"
tmp_file="${COOLDOWN_FILE}.tmp"
printf '{"last_restart_epoch": %s, "last_restart_reason": %s}\n' \
  "$now_epoch" \
  "$(jq -Rs . <<<"$decision")" |
  jq . >"$tmp_file"
mv "$tmp_file" "$COOLDOWN_FILE"
