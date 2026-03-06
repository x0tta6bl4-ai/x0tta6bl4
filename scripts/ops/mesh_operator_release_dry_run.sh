#!/usr/bin/env bash
set -euo pipefail

# mesh_operator_release_dry_run.sh
# --------------------------------
# Dry-run release validation with explicit checkpoints and report artifacts.

FAIL_FAST="${FAIL_FAST:-1}"
RUN_KIND_E2E="${RUN_KIND_E2E:-1}"
RUN_WEBHOOK_E2E="${RUN_WEBHOOK_E2E:-1}"
RUN_LIFECYCLE_E2E="${RUN_LIFECYCLE_E2E:-1}"
RUN_CANARY_ROLLBACK_E2E="${RUN_CANARY_ROLLBACK_E2E:-1}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
REPORT_DIR="${REPORT_DIR:-$REPO_ROOT/docs/release}"

TIMESTAMP_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
TIMESTAMP_ID="$(date -u +%Y%m%dT%H%M%SZ)"
LOG_FILE="$REPORT_DIR/mesh_operator_release_dry_run_${TIMESTAMP_ID}.log"
CHECKPOINTS_TSV="$REPORT_DIR/mesh_operator_release_dry_run_${TIMESTAMP_ID}.tsv"
REPORT_JSON="$REPORT_DIR/mesh_operator_release_dry_run_${TIMESTAMP_ID}.json"
REPORT_MD="$REPORT_DIR/mesh_operator_release_dry_run_${TIMESTAMP_ID}.md"
LATEST_MD="$REPORT_DIR/MESH_OPERATOR_RELEASE_DRY_RUN_LATEST.md"

mkdir -p "$REPORT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info() {
  echo -e "${GREEN}[INFO]${NC}  $*"
}

warn() {
  echo -e "${YELLOW}[WARN]${NC}  $*"
}

error() {
  echo -e "${RED}[ERROR]${NC} $*" >&2
}

run_checkpoint() {
  local id="$1"
  local name="$2"
  local cmd="$3"

  local started_epoch
  local ended_epoch
  local duration
  local rc=0
  local status="PASS"

  started_epoch="$(date +%s)"
  info "[${id}] ${name}"
  {
    echo ""
    echo "=== CHECKPOINT ${id}: ${name} ==="
    echo "COMMAND: ${cmd}"
    echo "START: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  } >>"$LOG_FILE"

  if ! bash -lc "cd '$REPO_ROOT' && ${cmd}" >>"$LOG_FILE" 2>&1; then
    rc=$?
    status="FAIL"
  fi

  ended_epoch="$(date +%s)"
  duration="$((ended_epoch - started_epoch))"

  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$id" "$name" "$status" "$duration" "$rc" "$cmd" >>"$CHECKPOINTS_TSV"

  if [[ "$status" == "PASS" ]]; then
    info "[${id}] PASS (${duration}s)"
  else
    error "[${id}] FAIL (${duration}s, rc=${rc})"
    if [[ "$FAIL_FAST" == "1" ]]; then
      return 1
    fi
  fi

  return 0
}

START_EPOCH="$(date +%s)"
START_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

cat >"$CHECKPOINTS_TSV" <<'TSV'
id	name	status	duration_seconds	rc	command
TSV

echo "mesh-operator release dry-run started at ${START_UTC}" >"$LOG_FILE"

overall_rc=0

run_checkpoint "CP-01" "Toolchain preflight" \
  "command -v kind >/dev/null && command -v kubectl >/dev/null && command -v helm >/dev/null && command -v docker >/dev/null && command -v go >/dev/null && docker info >/dev/null && kubectl config current-context >/dev/null" \
  || overall_rc=1

run_checkpoint "CP-02" "Version contract validation" \
  "python3 scripts/validate_version_contract.py" \
  || overall_rc=1

run_checkpoint "CP-03" "Mesh operator unit tests" \
  "cd mesh-operator && go test ./..." \
  || overall_rc=1

run_checkpoint "CP-04" "Fallback image reproducibility" \
  "bash scripts/ops/check_mesh_images_reproducibility.sh" \
  || overall_rc=1

run_checkpoint "CP-05" "Helm lint and webhook render" \
  "helm lint charts/x0tta-mesh-operator && helm template mesh-op charts/x0tta-mesh-operator --namespace x0tta-system --set operator.webhook.enabled=true --set operator.webhook.certManager.enabled=true >/tmp/mesh-operator-webhook-render.yaml" \
  || overall_rc=1

run_checkpoint "CP-06" "Git release promotion dry-run" \
  "bash scripts/release_to_main.sh --dry-run" \
  || overall_rc=1

if [[ "$RUN_KIND_E2E" == "1" ]]; then
  run_checkpoint "CP-07" "Kind smoke e2e" \
    "bash scripts/ops/mesh_operator_kind_e2e.sh" \
    || overall_rc=1
else
  warn "CP-07 skipped: RUN_KIND_E2E=0"
fi

if [[ "$RUN_WEBHOOK_E2E" == "1" ]]; then
  run_checkpoint "CP-08" "Webhook admission e2e" \
    "bash scripts/ops/mesh_operator_webhook_admission_e2e.sh" \
    || overall_rc=1
else
  warn "CP-08 skipped: RUN_WEBHOOK_E2E=0"
fi

if [[ "$RUN_LIFECYCLE_E2E" == "1" ]]; then
  run_checkpoint "CP-09" "Helm lifecycle e2e" \
    "bash scripts/ops/mesh_operator_helm_lifecycle_e2e.sh" \
    || overall_rc=1
else
  warn "CP-09 skipped: RUN_LIFECYCLE_E2E=0"
fi

if [[ "$RUN_CANARY_ROLLBACK_E2E" == "1" ]]; then
  run_checkpoint "CP-10" "Canary rollout + rollback e2e" \
    "bash scripts/ops/mesh_operator_canary_rollback_e2e.sh" \
    || overall_rc=1
else
  warn "CP-10 skipped: RUN_CANARY_ROLLBACK_E2E=0"
fi

END_EPOCH="$(date +%s)"
END_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
TOTAL_SECONDS="$((END_EPOCH - START_EPOCH))"
OVERALL_STATUS="PASS"
if [[ "$overall_rc" -ne 0 ]]; then
  OVERALL_STATUS="FAIL"
fi

python3 - "$CHECKPOINTS_TSV" "$REPORT_JSON" "$REPORT_MD" "$START_UTC" "$END_UTC" "$TOTAL_SECONDS" "$OVERALL_STATUS" <<'PY'
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

checkpoints_tsv = Path(sys.argv[1])
report_json = Path(sys.argv[2])
report_md = Path(sys.argv[3])
start_utc = sys.argv[4]
end_utc = sys.argv[5]
total_seconds = int(sys.argv[6])
overall_status = sys.argv[7]

rows: list[dict[str, str]] = []
with checkpoints_tsv.open("r", encoding="utf-8") as fh:
    reader = csv.DictReader(fh, delimiter="\t")
    for row in reader:
        if not row.get("id"):
            continue
        rows.append(row)

payload = {
    "scope": "mesh-operator release dry-run",
    "start_utc": start_utc,
    "end_utc": end_utc,
    "duration_seconds": total_seconds,
    "overall_status": overall_status,
    "checkpoints": [
        {
            "id": row["id"],
            "name": row["name"],
            "status": row["status"],
            "duration_seconds": int(row["duration_seconds"]),
            "rc": int(row["rc"]),
            "command": row["command"],
        }
        for row in rows
    ],
}
report_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

lines = [
    "# Mesh Operator Release Dry-Run Report",
    "",
    f"- **Start (UTC):** {start_utc}",
    f"- **End (UTC):** {end_utc}",
    f"- **Duration:** {total_seconds}s",
    f"- **Overall:** {overall_status}",
    "",
    "| Checkpoint | Status | Duration (s) |",
    "|---|---|---:|",
]
for row in rows:
    lines.append(f"| {row['id']} — {row['name']} | {row['status']} | {row['duration_seconds']} |")

report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY

cp "$REPORT_MD" "$LATEST_MD"

info "Dry-run report JSON: $REPORT_JSON"
info "Dry-run report MD:   $REPORT_MD"
info "Dry-run latest MD:   $LATEST_MD"
info "Dry-run log:         $LOG_FILE"

if [[ "$overall_rc" -ne 0 ]]; then
  error "Release dry-run failed"
  exit "$overall_rc"
fi

info "Release dry-run completed successfully"
