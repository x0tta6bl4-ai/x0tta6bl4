#!/usr/bin/env bash
# =============================================================================
# scripts/verify-v1.1.sh — v1.1 operator verification entrypoint
#
# Orchestrates all safe local checks and prints a three-bucket summary:
#   VERIFIED HERE         — ran and passed in this environment right now
#   VERIFIED VIA SCRIPT/CI — script exists, reproducible, not executed here
#   NOT VERIFIED YET      — blocked by hardware / credentials / environment
#
# Usage:
#   ./scripts/verify-v1.1.sh [--fast] [--json] [--help]
#
#   --fast   skip Python unit tests (they can take ~60 s)
#   --json   print final summary as JSON to stdout in addition to terminal
# =============================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ "${VERIFY_STABLE_COPY:-0}" != "1" ]]; then
  mkdir -p "${ROOT_DIR}/.tmp"
  STABLE_VERIFY_SCRIPT="${ROOT_DIR}/.tmp/verify-v1.1.$$.sh"
  cp "${ROOT_DIR}/scripts/verify-v1.1.sh" "${STABLE_VERIFY_SCRIPT}"
  VERIFY_STABLE_COPY=1 VERIFY_STABLE_COPY_PATH="${STABLE_VERIFY_SCRIPT}" exec bash "${STABLE_VERIFY_SCRIPT}" "$@"
fi

if [[ -n "${VERIFY_STABLE_COPY_PATH:-}" ]]; then
  trap 'rm -f "${VERIFY_STABLE_COPY_PATH}"' EXIT
fi

FAST=0
JSON=0
VERIFY_AGENT_NAME="${VERIFY_AGENT_NAME:-${AGENT_NAME:-lead-coordinator}}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --fast) FAST=1; shift ;;
    --json) JSON=1; shift ;;
    -h|--help)
      sed -n '2,15p' "$0" | sed 's/^# \?//'
      exit 0
      ;;
    *) echo "unknown argument: $1" >&2; exit 1 ;;
  esac
done

# -- terminal colours (disabled if not a tty) ---------------------------------
if [[ -t 1 ]]; then
  GRN='\033[0;32m'; YLW='\033[0;33m'; RED='\033[0;31m'; CYN='\033[0;36m'; RST='\033[0m'
else
  GRN=''; YLW=''; RED=''; CYN=''; RST=''
fi

# -- result tracking ----------------------------------------------------------
declare -a VERIFIED_HERE=()
declare -a VERIFIED_VIA_CI=()
declare -a NOT_VERIFIED=()
declare -a FAILED=()

pass()  { VERIFIED_HERE+=("$1");   echo -e "  ${GRN}PASS${RST}  $1"; }
ci()    { VERIFIED_VIA_CI+=("$1"); echo -e "  ${YLW}CI  ${RST}  $1"; }
skip()  { NOT_VERIFIED+=("$1");    echo -e "  ${CYN}SKIP${RST}  $1"; }
fail()  { FAILED+=("$1");          echo -e "  ${RED}FAIL${RST}  $1"; }

run_check() {
  local label="$1"; shift
  if "$@" >/dev/null 2>&1; then
    pass "${label}"
  else
    fail "${label}"
  fi
}

run_helm_lint_check() {
  local chart="$1"
  local output
  if output="$(helm lint "${chart}" --quiet 2>&1)"; then
    pass "helm lint ${chart}"
    return 0
  fi
  if printf '%s' "${output}" | grep -q "snap-confine is packaged without necessary permissions"; then
    skip "helm lint ${chart} — local helm is snap-confined; use charts/render-in-docker.sh"
    return 0
  fi
  fail "helm lint ${chart}"
}

run_ebpf_build_check() {
  local output
  mkdir -p "${ROOT_DIR}/.tmp/go-build"
  if output="$(
    cd "${ROOT_DIR}/ebpf/prod" && env GOCACHE="${ROOT_DIR}/.tmp/go-build" GOTOOLCHAIN=local go build ./... 2>&1
  )"; then
    pass "go build ./ebpf/prod (module-aware)"
    return 0
  fi
  if printf '%s' "${output}" | grep -q "requires go >="; then
    skip "go build ./ebpf/prod — local Go toolchain is older than ebpf/prod module requirement"
    if [[ -f "${ROOT_DIR}/ebpf/prod/build-in-docker.sh" ]]; then
      ci "ebpf/prod containerized build (ebpf/prod/build-in-docker.sh)"
    fi
    return 0
  fi
  fail "go build ./ebpf/prod (module-aware)"
}

run_benchmark_harness_check() {
  local output
  if output="$(bash "${ROOT_DIR}/ebpf/prod/benchmark-harness.sh" 2>&1)"; then
    pass "ebpf/prod/benchmark-harness.sh plan-only"
    return 0
  fi
  if printf '%s' "${output}" | grep -q "local Go toolchain cannot rebuild ebpf/prod source here"; then
    skip "ebpf/prod/benchmark-harness.sh plan-only — local source rebuild blocked by Go toolchain"
    if [[ -f "${ROOT_DIR}/ebpf/prod/build-in-docker.sh" ]]; then
      ci "ebpf/prod benchmark preflight with containerized build path"
    fi
    return 0
  fi
  fail "ebpf/prod/benchmark-harness.sh plan-only"
}

run_operator_packet_current_smoke_check() {
  local tmp
  tmp="$(mktemp)"
  if python3 -m src.integration.operator_evidence_packet --root . --output-json "${tmp}" --require-actionable >/dev/null 2>&1 \
    && python3 - "${tmp}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
summary = data.get("summary", {})
required_keys = {
    "external_settlement",
    "live_spire_mtls",
    "multi_host_mesh",
    "paid_client_path",
    "safe_rollout_rollback",
}
assert data.get("status") == "VERIFIED HERE"
assert data.get("ok") is True
assert data.get("decision") == "OPERATOR_ACTION_REQUIRED"
assert data.get("actionable") is True
assert data.get("goal_can_be_marked_complete") is False
assert data.get("selected_evidence_key") in required_keys
assert summary.get("commands_total", 0) > 0
assert summary.get("commands_missing_entrypoints") == 0
assert summary.get("operator_action_required") is True
PY
  then
    pass "integration-spine operator packet current shards are actionable"
  else
    fail "integration-spine operator packet current shards are actionable"
  fi
  rm -f "${tmp}"
}

run_operator_packet_index_current_smoke_check() {
  local tmp
  tmp="$(mktemp)"
  if python3 -m src.integration.operator_evidence_packet --root . --all-blockers --output-json "${tmp}" --require-all-actionable >/dev/null 2>&1 \
    && python3 - "${tmp}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
summary = data.get("summary", {})
assert data.get("status") == "VERIFIED HERE"
assert data.get("ok") is True
assert data.get("decision") == "ALL_OPERATOR_PACKETS_ACTIONABLE"
assert data.get("all_packets_actionable") is True
assert data.get("local_handoff_complete") is True
assert data.get("goal_can_be_marked_complete") is False
assert summary.get("packets_total", 0) > 0
assert summary.get("actionable_packets", 0) > 0
assert summary.get("actionable_packets") == summary.get("packets_total")
assert summary.get("packets_with_missing_entrypoints") == 0
assert summary.get("commands_missing_entrypoints_total") == 0
assert summary.get("missing_local_required_artifacts_total") == 0
assert summary.get("missing_operator_required_artifacts_total", 0) > 0
assert summary.get("missing_required_artifacts_total") == summary.get("missing_operator_required_artifacts_total")
PY
  then
    pass "integration-spine operator packet index current shards are actionable"
  else
    fail "integration-spine operator packet index current shards are actionable"
  fi
  rm -f "${tmp}"
}

run_external_settlement_preflight_current_smoke_check() {
  local tmp code
  tmp="$(mktemp)"
  set +e
  python3 -m src.integration.external_settlement \
    --root . \
    --preflight-capture-inputs \
    --transaction-hash "" \
    --destination-chain base-sepolia \
    --settlement-id "" \
    --rpc-url "" \
    --output-preflight-json "${tmp}" \
    --require-preflight-ready >/dev/null 2>&1
  code=$?
  set -e
  if [[ "${code}" -eq 2 ]] && python3 - "${tmp}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
summary = data.get("summary", {})
assert data.get("status") == "VERIFIED HERE"
assert data.get("ok") is True
assert data.get("decision") == "CAPTURE_INPUTS_BLOCKED"
assert data.get("goal_can_be_marked_complete") is False
assert data.get("runs_live_rpc") is False
assert data.get("materializes_evidence") is False
assert summary.get("capture_inputs_ready") is False
assert summary.get("errors_total", 0) > 0
PY
  then
    pass "integration-spine external settlement capture preflight fails closed"
  else
    fail "integration-spine external settlement capture preflight fails closed"
  fi
  rm -f "${tmp}"
}

run_external_settlement_scaffold_current_smoke_check() {
  local tmp template_dir
  tmp="$(mktemp)"
  template_dir="$(mktemp -d)"
  if python3 scripts/ops/scaffold_x0t_external_settlement_evidence.py \
      --root . \
      --template-dir "${template_dir}" \
      --expected-evidence .tmp/external-settlement-evidence/settlement-submit.json \
      --output-json "${tmp}" \
      --write-template-files \
      --force \
      --require-written >/dev/null 2>&1 \
    && python3 - "${tmp}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
summary = data.get("summary", {})
assert data.get("status") == "VERIFIED HERE"
assert data.get("ok") is True
assert data.get("scaffold_decision") == "TEMPLATE_ONLY_NOT_EVIDENCE"
assert data.get("goal_can_be_marked_complete") is False
assert data.get("materializes_evidence") is False
assert data.get("runs_live_rpc") is False
assert data.get("submits_transaction") is False
assert data.get("mutates_vpn_runtime") is False
assert summary.get("template_files_total") == 3
assert summary.get("template_files_written") == 3
assert summary.get("templates_marked_not_evidence") is True
assert summary.get("expected_evidence_file_exists") is False
assert summary.get("template_validation_rejects_as_evidence") is True
PY
  then
    pass "integration-spine external settlement scaffold writes templates only"
  else
    fail "integration-spine external settlement scaffold writes templates only"
  fi
  rm -f "${tmp}"
  rm -rf "${template_dir}"
}

run_external_settlement_template_retained_rejection_smoke_check() {
  local temp_root scaffold_report verifier_report code
  temp_root="$(mktemp -d)"
  scaffold_report="${temp_root}/external-settlement-scaffold-report.json"
  verifier_report="${temp_root}/external-settlement-verifier-report.json"

  if python3 scripts/ops/scaffold_x0t_external_settlement_evidence.py \
      --root "${temp_root}" \
      --template-dir template-pack \
      --expected-evidence external-settlement-evidence/settlement-submit.json \
      --output-json "${scaffold_report}" \
      --write-template-files \
      --force \
      --require-written >/dev/null 2>&1 \
    && mkdir -p "${temp_root}/external-settlement-evidence" \
    && cp "${temp_root}/template-pack/settlement-submit.template.json" \
      "${temp_root}/external-settlement-evidence/settlement-submit.json"
  then
    set +e
    python3 scripts/ops/verify_x0t_external_settlement_evidence.py \
      --root "${temp_root}" \
      --evidence external-settlement-evidence/settlement-submit.json \
      --output-json "${verifier_report}" \
      --require-ready >/dev/null 2>&1
    code=$?
    set -e
    if [[ "${code}" -eq 2 ]] && python3 - "${scaffold_report}" "${verifier_report}" <<'PY'
import json
import sys

scaffold = json.load(open(sys.argv[1], encoding="utf-8"))
report = json.load(open(sys.argv[2], encoding="utf-8"))
summary = report.get("summary", {})
errors = "\n".join(report.get("evidence_file", {}).get("errors", []))

assert scaffold.get("scaffold_decision") == "TEMPLATE_ONLY_NOT_EVIDENCE"
assert scaffold.get("materializes_evidence") is False
assert scaffold.get("runs_live_rpc") is False
assert scaffold.get("submits_transaction") is False
assert scaffold.get("summary", {}).get("template_validation_rejects_as_evidence") is True
assert report.get("status") == "VERIFIED HERE"
assert report.get("x0t_external_settlement_decision") == "BLOCKED"
assert report.get("goal_can_be_marked_complete") is False
assert summary.get("x0t_external_settlement_ready") is False
assert summary.get("evidence_file_invalid") is True
assert report.get("evidence_file", {}).get("status") == "INVALID"
assert "template_only must not be true" in errors
PY
    then
      pass "integration-spine external settlement template is rejected as retained evidence"
    else
      fail "integration-spine external settlement template is rejected as retained evidence"
    fi
  else
    fail "integration-spine external settlement template is rejected as retained evidence"
  fi
  rm -rf "${temp_root}"
}

run_external_settlement_operator_handoff_current_smoke_check() {
  local tmp code
  tmp="$(mktemp)"
  set +e
  python3 -m src.integration.external_settlement_operator_handoff --root . --output-json "${tmp}" --require-ready >/dev/null 2>&1
  code=$?
  set -e
  if [[ "${code}" -eq 2 ]] && python3 - "${tmp}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
summary = data.get("summary", {})
assert data.get("status") == "VERIFIED HERE"
assert data.get("ok") is True
assert str(data.get("schema_version", "")).endswith("v6-repo-generated")
assert "source-restored" not in str(data.get("schema_version", ""))
assert data.get("handoff_decision") == "X0T_EXTERNAL_SETTLEMENT_HANDOFF_BLOCKED_ON_OPERATOR"
assert data.get("ready_for_completion_rerun") is False
assert data.get("goal_can_be_marked_complete") is False
assert data.get("mutates_chain") is False
assert data.get("runs_live_rpc") is False
assert data.get("submits_transaction") is False
assert summary.get("source_errors_total") == 0
assert summary.get("capture_preflight_available") is True
assert summary.get("capture_preflight_decision") == "CAPTURE_INPUTS_BLOCKED"
assert summary.get("capture_inputs_ready") is False
assert summary.get("evidence_file_ready") is False
assert summary.get("live_rpc_ready") is False
assert summary.get("production_import_external_settlement_ready") is False
assert summary.get("completion_gate_external_settlement_ready") is False
assert summary.get("missing_inputs_total", 0) > 0
assert summary.get("missing_inputs_operator_input_required") == summary.get("missing_inputs_total")
assert summary.get("missing_inputs_generic_operator_required") == 0
assert summary.get("operator_actions_total") == 6
assert summary.get("operator_commands_total") == 5
assert summary.get("operator_command_entrypoints_missing") == 0
assert summary.get("operator_command_surface_ready") is True
assert summary.get("operator_commands_with_shell_redirection_placeholders") == 0
assert summary.get("operator_command_shell_surface_ready") is True
assert summary.get("operator_sequence_ready") is True
assert data.get("missing_inputs")
assert data.get("missing_inputs")[0].get("id") == "capture_input_preflight"
assert {
    item.get("status")
    for item in data.get("missing_inputs", [])
    if isinstance(item, dict)
} == {"OPERATOR_INPUT_REQUIRED"}
assert data.get("operator_next_actions")
assert data.get("operator_next_actions")[0].get("id") == "preflight_capture_inputs"
assert data.get("operator_next_actions")[0].get("status") == "OPERATOR_INPUT_REQUIRED"
assert data.get("operator_next_actions")[0].get("runs_live_rpc") is False
assert data.get("operator_next_actions")[0].get("writes_evidence") is False
assert all(
    item.get("status") in {"OPERATOR_INPUT_REQUIRED", "DONE"}
    for item in data.get("operator_next_actions", [])
)
assert data.get("operator_command_checks")
assert all(item.get("entrypoint_exists") is True for item in data.get("operator_command_checks", []))
assert all(item.get("shell_redirection_placeholder_detected") is False for item in data.get("operator_command_checks", []))
commands = [item.get("command", "") for item in data.get("operator_next_actions", [])]
assert any('"$X0T_BASE_RPC_URL"' in command for command in commands)
assert not any("<base-rpc-url>" in command for command in commands)
PY
  then
    pass "integration-spine external settlement operator handoff current shards fail closed"
  else
    fail "integration-spine external settlement operator handoff current shards fail closed"
  fi
  rm -f "${tmp}"
}

run_operator_bundle_secret_scan_current_smoke_check() {
  local tmp
  tmp="$(mktemp)"
  if python3 -m src.integration.operator_bundle_secret_scan --root . --output-json "${tmp}" --require-clear >/dev/null 2>&1 \
    && python3 - "${tmp}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
summary = data.get("summary", {})
assert data.get("status") == "VERIFIED HERE"
assert data.get("ok") is True
assert data.get("secret_scan_decision") == "OPERATOR_BUNDLE_SECRET_SCAN_CLEAR"
assert data.get("ready_for_stage") is True
assert data.get("goal_can_be_marked_complete") is False
assert data.get("mutates_files") is False
assert summary.get("source_errors_total") == 0
assert summary.get("secret_scan_findings") == 0
assert summary.get("secret_scan_clear") is True
assert summary.get("return_packet_json_valid") is True
PY
  then
    pass "integration-spine operator bundle secret scan current shards are clear"
  else
    fail "integration-spine operator bundle secret scan current shards are clear"
  fi
  rm -f "${tmp}"
}

run_production_input_return_packet_current_smoke_check() {
  local tmp code
  tmp="$(mktemp)"
  set +e
  python3 -m src.integration.production_input_return_packet --root . --output-json "${tmp}" --require-ready >/dev/null 2>&1
  code=$?
  set -e
  if [[ "${code}" -eq 2 ]] && python3 - "${tmp}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
summary = data.get("summary", {})
assert data.get("status") == "VERIFIED HERE"
assert data.get("ok") is True
assert str(data.get("schema_version", "")).endswith("v2-repo-generated")
assert data.get("decision") == "RETURN_PACKET_BLOCKED_ON_OPERATOR_EVIDENCE"
assert data.get("goal_can_be_marked_complete") is False
assert data.get("mutates_files") is False
assert data.get("runs_live_rpc") is False
assert data.get("submits_transaction") is False
assert summary.get("source_errors_total") == 0
assert summary.get("blocking_inputs_total") == 31
assert summary.get("blocking_raw_inputs") == 30
assert summary.get("blocking_external_inputs") == 1
assert summary.get("blocking_inputs_operator_input_required") == 31
assert summary.get("blocking_inputs_generic_operator_required") == 0
assert summary.get("raw_files_expected") == 63
assert summary.get("raw_files_missing") == 33
assert summary.get("raw_files_local_observation") == 30
assert summary.get("external_artifacts_operator_required") == 1
assert summary.get("external_settlement_live_rpc_ready") is False
assert summary.get("operator_next_actions_total") == 2
assert summary.get("operator_next_actions_operator_input_required") == 2
assert summary.get("operator_next_actions_generic_blocking") == 0
actions = data.get("operator_next_actions", [])
assert {item.get("id") for item in actions if isinstance(item, dict)} == {
    "replace_raw_local_observation_evidence",
    "replace_external_settlement_template",
}
assert {
    item.get("status")
    for item in actions
    if isinstance(item, dict)
} == {"OPERATOR_INPUT_REQUIRED"}
PY
  then
    pass "integration-spine production input return packet current shards fail closed"
  else
    fail "integration-spine production input return packet current shards fail closed"
  fi
  rm -f "${tmp}"
}

run_live_rollout_image_provenance_scaffold_current_smoke_check() {
  local tmp template_dir expected_evidence
  tmp="$(mktemp)"
  template_dir="$(mktemp -d)"
  expected_evidence="${template_dir}/expected-image-digests.json"
  if python3 scripts/ops/scaffold_live_rollout_image_provenance_evidence.py \
      --root . \
      --template-dir "${template_dir}" \
      --expected-evidence "${expected_evidence}" \
      --output-json "${tmp}" \
      --write-template-files \
      --force \
      --require-written >/dev/null 2>&1 \
    && python3 - "${tmp}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
summary = data.get("summary", {})
assert data.get("status") == "VERIFIED HERE"
assert data.get("ok") is True
assert data.get("scaffold_decision") == "TEMPLATE_ONLY_NOT_EVIDENCE"
assert data.get("goal_can_be_marked_complete") is False
assert data.get("materializes_evidence") is False
assert data.get("contacts_registry") is False
assert data.get("contacts_cluster") is False
assert data.get("runs_cosign") is False
assert data.get("mutates_vpn_runtime") is False
assert summary.get("template_files_total") == 4
assert summary.get("template_files_written") == 4
assert summary.get("templates_marked_not_evidence") is True
assert summary.get("expected_evidence_file_exists") is False
assert summary.get("template_validation_rejects_as_rollout_evidence") is True
assert summary.get("current_runtime_tag_refs_total") == 7
PY
  then
    pass "integration-spine live rollout image provenance scaffold writes templates only"
  else
    fail "integration-spine live rollout image provenance scaffold writes templates only"
  fi
  rm -f "${tmp}"
  rm -rf "${template_dir}"
}

run_production_raw_evidence_template_pack_current_smoke_check() {
  local tmp template_dir
  tmp="$(mktemp)"
  template_dir="$(mktemp -d)"
  if python3 scripts/ops/generate_production_raw_evidence_template_pack.py \
      --root . \
      --template-dir "${template_dir}" \
      --output-json "${tmp}" \
      --write-template-files \
      --force \
      --require-written >/dev/null 2>&1 \
    && python3 - "${tmp}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
summary = data.get("summary", {})
assert data.get("status") == "VERIFIED HERE"
assert data.get("ok") is True
assert data.get("scaffold_decision") == "TEMPLATE_ONLY_NOT_EVIDENCE"
assert data.get("goal_can_be_marked_complete") is False
assert data.get("materializes_evidence") is False
assert data.get("installs_raw_evidence") is False
assert data.get("runs_collectors") is False
assert data.get("runs_live_cluster") is False
assert data.get("mutates_vpn_runtime") is False
assert summary.get("raw_template_files_total", 0) > 0
assert summary.get("template_files_total") == summary.get("raw_template_files_total") + 2
assert summary.get("template_files_written") == summary.get("template_files_total")
assert summary.get("templates_marked_not_evidence") is True
assert summary.get("expected_operator_bundle_files_total") == summary.get("raw_template_files_total")
assert summary.get("source_errors_total") == 0
PY
  then
    pass "integration-spine production raw evidence template pack writes templates only"
  else
    fail "integration-spine production raw evidence template pack writes templates only"
  fi
  rm -f "${tmp}"
  rm -rf "${template_dir}"
}

run_production_raw_evidence_template_rejection_smoke_check() {
  local temp_root generator_report import_report code
  temp_root="$(mktemp -d)"
  generator_report="${temp_root}/template-pack-report.json"
  import_report="${temp_root}/raw-import-report.json"

  if python3 - "${temp_root}" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
collector_by_key = {
    "live_spire_mtls": "zero-trust-pqc",
    "multi_host_mesh": "self-healing-pqc-mesh",
    "paid_client_path": "paid-client-serviceability",
    "safe_rollout_rollback": "live-rollout",
}

manifest = {
    "collectors": [
        {
            "collector_id": collector_id,
            "raw_files": [
                {
                    "raw_id": f"{collector_id}/operator-manifest.json",
                    "file_name": "operator-manifest.json",
                    "path": f".tmp/{collector_id}-raw-evidence/operator-manifest.json",
                }
            ],
        }
        for collector_id in sorted(collector_by_key.values())
    ]
}
passport = {
    "required_evidence_files": [
        {
            "kind": "raw_evidence",
            "evidence_key": evidence_key,
            "raw_id": f"{collector_id}/operator-manifest.json",
            "operator_return_path": f"operator-bundle/{collector_id}/operator-manifest.json",
            "retained_destination_path": f".tmp/{collector_id}-raw-evidence/operator-manifest.json",
            "required_statuses": ["VERIFIED HERE"],
            "required_operator_provenance_fields": ["collected_at", "collected_by", "source_commands"],
        }
        for evidence_key, collector_id in collector_by_key.items()
    ]
}
semantic = {"status": "VERIFIED HERE", "summary": {"by_collector": {}}}

def write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")

write(root / ".tmp/validation-shards/production-raw-evidence-intake-manifest-current.json", manifest)
write(root / ".tmp/validation-shards/integration-spine-semantic-production-blocker-queue-current.json", semantic)
write(root / "passport.json", passport)
PY
  then
    if python3 scripts/ops/generate_production_raw_evidence_template_pack.py \
        --root "${temp_root}" \
        --passport "${temp_root}/passport.json" \
        --template-dir operator-bundle \
        --operator-bundle-root operator-bundle \
        --output-json "${generator_report}" \
        --write-template-files \
        --force \
        --require-written >/dev/null 2>&1
    then
      set +e
      python3 scripts/ops/import_production_raw_evidence_bundle.py \
        --root "${temp_root}" \
        --bundle-root operator-bundle \
        --output-json "${import_report}" \
        --require-ready >/dev/null 2>&1
      code=$?
      set -e
      if [[ "${code}" -eq 2 ]] && python3 - "${generator_report}" "${import_report}" <<'PY'
import json
import sys

generated = json.load(open(sys.argv[1], encoding="utf-8"))
report = json.load(open(sys.argv[2], encoding="utf-8"))
generated_summary = generated.get("summary", {})
summary = report.get("summary", {})
reports = report.get("evidence_key_reports", [])
blocking_text = json.dumps(report.get("evidence_key_reports", []))

assert generated.get("scaffold_decision") == "TEMPLATE_ONLY_NOT_EVIDENCE"
assert generated.get("materializes_evidence") is False
assert generated_summary.get("raw_template_files_total") == 4
assert generated_summary.get("template_files_written") == generated_summary.get("template_files_total")
assert generated_summary.get("templates_marked_not_evidence") is True
assert report.get("raw_evidence_bundle_import_decision") == "BLOCKED"
assert report.get("installs_raw_evidence") is False
assert report.get("mutates_vpn_runtime") is False
assert summary.get("source_files_total") == 4
assert summary.get("source_files_found") == 4
assert summary.get("collectors_ready") == 0
assert summary.get("ready_to_install") is False
assert "template/mock/placeholder markers must be absent" in blocking_text
assert "production_ready must be true for source-candidate promotion" in blocking_text
PY
      then
        pass "integration-spine production raw evidence templates are rejected as operator bundle evidence"
      else
        fail "integration-spine production raw evidence templates are rejected as operator bundle evidence"
      fi
    else
      fail "integration-spine production raw evidence templates are rejected as operator bundle evidence"
    fi
  else
    fail "integration-spine production raw evidence templates are rejected as operator bundle evidence"
  fi
  rm -rf "${temp_root}"
}

run_live_rollout_image_template_bundle_rejection_smoke_check() {
  local temp_root scaffold_report import_report code
  temp_root="$(mktemp -d)"
  scaffold_report="${temp_root}/rollout-scaffold-report.json"
  import_report="${temp_root}/raw-import-report.json"

  if python3 - "${temp_root}" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
collector_files = {
    "billing-provisioning": ["operator-manifest.json"],
    "ebpf-observability": ["operator-manifest.json"],
    "zero-trust-pqc": ["operator-manifest.json"],
    "self-healing-pqc-mesh": ["operator-manifest.json"],
    "paid-client-serviceability": ["operator-manifest.json"],
    "live-rollout": [
        "operator-manifest.json",
        "argocd-app-get.json",
        "kubectl-rollout-status.json",
        "rollback-drill.json",
        "admission-allow-deny.json",
        "image-digests.json",
    ],
    "signed-release-provenance": ["operator-manifest.json"],
    "sla-telemetry": ["operator-manifest.json"],
    "stable-deploy": ["operator-manifest.json"],
}

manifest = {
    "collectors": [
        {
            "collector_id": collector_id,
            "raw_files": [
                {
                    "raw_id": f"{collector_id}/{file_name}",
                    "file_name": file_name,
                    "path": f".tmp/{collector_id}-raw-evidence/{file_name}",
                }
                for file_name in file_names
            ],
        }
        for collector_id, file_names in collector_files.items()
    ]
}
semantic = {"status": "VERIFIED HERE", "summary": {"by_collector": {}}}

def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")

write_json(root / ".tmp/validation-shards/production-raw-evidence-intake-manifest-current.json", manifest)
write_json(root / ".tmp/validation-shards/integration-spine-semantic-production-blocker-queue-current.json", semantic)

for collector_id, file_names in collector_files.items():
    for file_name in file_names:
        write_json(
            root / "operator-bundle" / collector_id / file_name,
            {
                "status": "VERIFIED HERE",
                "evidence_status": "VERIFIED HERE",
                "collector_id": collector_id,
                "raw_id": f"{collector_id}/{file_name}",
                "file_name": file_name,
                "collected_at": "2026-05-20T00:00:00Z",
                "collected_by": "production-operator-2026-05-20",
                "source_commands": [f"kubectl --context prod get {collector_id} {file_name} -o json"],
                "production_ready": True,
                "production_promotion_blockers": [],
                "environment": "production",
            },
        )
PY
  then
    if python3 scripts/ops/scaffold_live_rollout_image_provenance_evidence.py \
        --root "${temp_root}" \
        --template-dir rollout-template \
        --expected-evidence operator-bundle/live-rollout/image-digests.json \
        --output-json "${scaffold_report}" \
        --write-template-files \
        --force \
        --require-written >/dev/null 2>&1 \
      && python3 - "${temp_root}" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
template = root / "rollout-template/image-digests.template.json"
target = root / "operator-bundle/live-rollout/image-digests.json"
target.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
PY
    then
      set +e
      python3 scripts/ops/import_production_raw_evidence_bundle.py \
        --root "${temp_root}" \
        --bundle-root operator-bundle \
        --output-json "${import_report}" \
        --require-ready >/dev/null 2>&1
      code=$?
      set -e
      if [[ "${code}" -eq 2 ]] && python3 - "${scaffold_report}" "${import_report}" <<'PY'
import json
import sys

scaffold = json.load(open(sys.argv[1], encoding="utf-8"))
report = json.load(open(sys.argv[2], encoding="utf-8"))
summary = report.get("summary", {})
reports = report.get("evidence_key_reports", [])
blocking_text = json.dumps(report.get("evidence_key_reports", []))

assert scaffold.get("scaffold_decision") == "TEMPLATE_ONLY_NOT_EVIDENCE"
assert scaffold.get("materializes_evidence") is False
assert scaffold.get("contacts_registry") is False
assert scaffold.get("contacts_cluster") is False
assert scaffold.get("runs_cosign") is False
assert scaffold.get("summary", {}).get("template_validation_rejects_as_rollout_evidence") is True
assert report.get("raw_evidence_bundle_import_decision") == "BLOCKED"
assert report.get("installs_raw_evidence") is False
assert len(reports) == 9
assert summary.get("source_files_total") == 14
assert summary.get("source_files_found") == 14
assert summary.get("collectors_ready") == len(reports) - 1
assert summary.get("collectors_blocked") == 1
assert summary.get("ready_to_install") is False
assert "operator-bundle/live-rollout/image-digests.json" in blocking_text
assert "template/mock/placeholder markers must be absent" in blocking_text
assert "production_ready must be true for source-candidate promotion" in blocking_text
PY
      then
        pass "integration-spine live rollout image template is rejected as operator bundle evidence"
      else
        fail "integration-spine live rollout image template is rejected as operator bundle evidence"
      fi
    else
      fail "integration-spine live rollout image template is rejected as operator bundle evidence"
    fi
  else
    fail "integration-spine live rollout image template is rejected as operator bundle evidence"
  fi
  rm -rf "${temp_root}"
}

run_scaffold_retained_raw_prefill_current_smoke_check() {
  local tmp code
  tmp="$(mktemp)"
  set +e
  python3 -m src.integration.scaffold_retained_raw_prefill --root . --output-json "${tmp}" --require-ready >/dev/null 2>&1
  code=$?
  set -e
  if [[ "${code}" -eq 2 ]] && python3 - "${tmp}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
summary = data.get("summary", {})
assert data.get("status") == "VERIFIED HERE"
assert data.get("ok") is True
assert str(data.get("schema_version", "")).endswith("v4-repo-generated")
assert "source-restored" not in str(data.get("schema_version", ""))
assert data.get("prefill_decision") == "PREFILL_BLOCKED_ON_RETAINED_RAW_EVIDENCE"
assert data.get("ready") is False
assert data.get("goal_can_be_marked_complete") is False
assert data.get("mutates_files") is False
assert data.get("touches_external_settlement") is False
assert summary.get("source_errors") == 0
assert summary.get("raw_files_expected", 0) > 0
assert summary.get("raw_files_destination_exists", 0) > 0
assert summary.get("raw_files_already_filled") == 0
assert summary.get("raw_files_ready_to_prefill") == 0
assert summary.get("raw_files_invalid_evidence", 0) > 0
assert summary.get("raw_files_local_observation", 0) > 0
assert summary.get("blocking_raw_files", 0) > 0
PY
  then
    pass "integration-spine scaffold retained raw prefill current shards fail closed"
  else
    fail "integration-spine scaffold retained raw prefill current shards fail closed"
  fi
  rm -f "${tmp}"
}

run_source_runtime_surface_current_smoke_check() {
  local tmp
  tmp="$(mktemp)"
  if python3 -m src.integration.source_runtime_surface --root . --output-json "${tmp}" --require-ready >/dev/null 2>&1 && python3 - "${tmp}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
summary = data.get("summary", {})
assert data.get("status") == "VERIFIED HERE"
assert data.get("ok") is True
assert str(data.get("schema_version", "")).endswith("v3-repo-generated")
assert "source-restored" not in str(data.get("schema_version", ""))
assert data.get("decision") == "SOURCE_RUNTIME_SURFACE_READY"
assert data.get("ready") is True
assert data.get("goal_can_be_marked_complete") is False
assert data.get("mutates_files") is False
assert data.get("contacts_live_systems") is False
assert summary.get("critical_scripts_total", 0) > 0
assert summary.get("critical_sources_missing") == 0
assert summary.get("critical_source_compile_errors") == 0
assert summary.get("critical_source_backed") == summary.get("critical_scripts_total")
assert summary.get("source_errors_total") == 0
assert summary.get("goal_can_be_marked_complete") is False
PY
  then
    pass "integration-spine source runtime surface current shards are repo-backed"
  else
    fail "integration-spine source runtime surface current shards are repo-backed"
  fi
  rm -f "${tmp}"
}

run_current_shard_stale_guard_smoke_check() {
  local tmp
  tmp="$(mktemp)"
  if python3 -m src.integration.current_shard_stale_guard --root . --output-json "${tmp}" --require-clear >/dev/null 2>&1 && python3 - "${tmp}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
summary = data.get("summary", {})
assert data.get("status") == "VERIFIED HERE"
assert data.get("ok") is True
assert str(data.get("schema_version", "")).endswith("v1-repo-generated")
assert data.get("decision") == "CURRENT_SHARDS_CLEAR"
assert data.get("ready") is True
assert data.get("goal_can_be_marked_complete") is False
assert data.get("mutates_files") is False
assert data.get("contacts_live_systems") is False
assert summary.get("current_shards_scanned", 0) > 0
assert summary.get("load_errors_total") == 0
assert summary.get("findings_total") == 0
assert summary.get("source_restored_markers") == 0
assert summary.get("generic_status_blocking") == 0
assert summary.get("legacy_status_map_operator_required") == 0
assert summary.get("legacy_status_map_operator_inputs_required") == 0
assert summary.get("generic_status_operator_required") == 0
assert summary.get("legacy_status_operator_inputs_required", 0) <= 1
assert summary.get("legacy_status_blocked", 0) <= 5
assert summary.get("config_required_status") == 0
assert summary.get("stale_completion_audit_count_markers") == 0
assert summary.get("raw_install_count_contradictions") == 0
PY
  then
    pass "integration-spine current shard stale marker guard is clear"
  else
    fail "integration-spine current shard stale marker guard is clear"
  fi
  rm -f "${tmp}"
}

run_stale_roadmap_entrypoint_triage_smoke_check() {
  local tmp
  tmp="$(mktemp)"
  if python3 -m src.integration.stale_roadmap_audit_entrypoint_check --root . --output-json "${tmp}" --require-triaged >/dev/null 2>&1 && python3 - "${tmp}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
summary = data.get("summary", {})
assert data.get("status") == "VERIFIED HERE"
assert data.get("ok") is True
assert str(data.get("schema_version", "")).endswith("v1-repo-generated")
assert data.get("decision") == "STALE_AUDIT_ENTRYPOINTS_TRIAGED"
assert data.get("ready") is False
assert data.get("triage_ready") is True
assert data.get("goal_can_be_marked_complete") is False
assert data.get("mutates_files") is False
assert data.get("contacts_live_systems") is False
assert summary.get("artifacts_loaded") == summary.get("artifacts_total")
assert summary.get("entrypoints_missing_total", 0) > 0
assert summary.get("missing_entrypoints_unclassified") == 0
assert summary.get("current_entrypoint_targets_seen_total", 0) > 0
assert summary.get("current_entrypoint_targets_present_total") == summary.get("current_entrypoint_targets_seen_total")
assert summary.get("current_entrypoint_targets_missing_total") == 0
PY
  then
    pass "integration-spine stale roadmap entrypoints are fully triaged"
  else
    fail "integration-spine stale roadmap entrypoints are fully triaged"
  fi
  rm -f "${tmp}"
}

run_semantic_queue_current_smoke_check() {
  local tmp code
  tmp="$(mktemp)"
  set +e
  python3 -m src.integration.semantic_production_blocker_queue --root . --output-json "${tmp}" --require-clear >/dev/null 2>&1
  code=$?
  set -e
  if [[ "${code}" -eq 2 ]] && python3 - "${tmp}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
summary = data.get("summary", {})
assert data.get("status") == "VERIFIED HERE"
assert data.get("ok") is True
assert data.get("completion_decision") == "NOT_COMPLETE"
assert data.get("goal_can_be_marked_complete") is False
assert summary.get("source_errors_total") == 0
assert summary.get("blocking_items_total") == 121
assert summary.get("blocking_items_operator_input_required") == 121
assert summary.get("blocking_items_generic_blocking") == 0
assert summary.get("semantic_preflight_errors_total") == 120
assert summary.get("raw_install_claim_source") == "return_acceptance"
assert summary.get("current_raw_files_installed") == 0
assert summary.get("pipeline_raw_files_reported_installed") == 0
assert summary.get("return_acceptance_raw_files_local_observation", 0) > 0
assert summary.get("return_acceptance_raw_ready_to_stage") is False
assert data.get("blocking_items")
assert data.get("priority_order")
statuses = {
    item.get("status")
    for item in data.get("blocking_items", [])
    if isinstance(item, dict)
}
assert statuses == {"OPERATOR_INPUT_REQUIRED"}
PY
  then
    pass "integration-spine semantic production blocker queue current shards fail closed"
  else
    fail "integration-spine semantic production blocker queue current shards fail closed"
  fi
  rm -f "${tmp}"
}

run_raw_evidence_inventory_current_smoke_check() {
  local tmp code
  tmp="$(mktemp)"
  set +e
  python3 -m src.integration.raw_evidence_inventory --root . --output-json "${tmp}" --require-ready >/dev/null 2>&1
  code=$?
  set -e
  if [[ "${code}" -eq 2 ]] && python3 - "${tmp}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
summary = data.get("summary", {})
assert data.get("status") == "VERIFIED HERE"
assert data.get("ok") is True
assert data.get("completion_decision") == "NOT_COMPLETE"
assert data.get("goal_can_be_marked_complete") is False
assert summary.get("source_errors_total") == 0
assert summary.get("files_total", 0) > 0
assert summary.get("raw_install_claim_source") == "return_acceptance"
assert summary.get("pipeline_raw_files_expected", 0) >= summary.get("files_total", 0)
assert summary.get("pipeline_raw_files_reported_installed") == 0
assert summary.get("pipeline_raw_files_installed") == 0
assert summary.get("return_acceptance_raw_files_expected") == summary.get("pipeline_raw_files_expected")
assert summary.get("return_acceptance_raw_files_staged") == 0
assert summary.get("return_acceptance_raw_files_local_observation", 0) > 0
assert summary.get("return_acceptance_raw_ready_to_stage") is False
assert summary.get("usable_for_goal_completion_files", 0) < summary.get("files_total", 0)
assert summary.get("semantic_blockers_total", 0) > 0
assert data.get("records")
PY
  then
    pass "integration-spine raw evidence inventory current shards fail closed"
  else
    fail "integration-spine raw evidence inventory current shards fail closed"
  fi
  rm -f "${tmp}"
}

run_current_evidence_rollup_current_smoke_check() {
  local tmp code
  tmp="$(mktemp)"
  set +e
  python3 -m src.integration.current_evidence_rollup --root . --output-json "${tmp}" --require-complete >/dev/null 2>&1
  code=$?
  set -e
  if [[ "${code}" -eq 2 ]] && python3 - "${tmp}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
summary = data.get("summary", {})
assert data.get("status") == "VERIFIED HERE"
assert data.get("ok") is True
assert data.get("completion_decision") == "NOT_COMPLETE"
assert data.get("goal_can_be_marked_complete") is False
assert summary.get("source_errors_total") == 0
assert summary.get("top_blockers_total", 0) > 0
assert summary.get("top_blockers_blocking") == 0
assert summary.get("top_blockers_operator_input_required") == 4
assert summary.get("top_blockers_operator_approval_required") == 1
assert summary.get("x0t_contract_surface_clear") is True
assert summary.get("x0t_contract_deployment_ready") is False
assert summary.get("x0t_contract_readiness_decision") == "BLOCKED_ON_DEPLOYMENT_CONFIG"
assert summary.get("x0t_bridge_config_decision") == "X0T_BRIDGE_CONFIG_BLOCKED_ON_OPERATOR"
assert summary.get("external_settlement_ready") is False
assert summary.get("external_settlement_handoff_available") is True
assert summary.get("external_settlement_handoff_clear") is True
assert summary.get("external_settlement_handoff_decision") == "X0T_EXTERNAL_SETTLEMENT_HANDOFF_BLOCKED_ON_OPERATOR"
assert summary.get("external_settlement_handoff_ready_for_completion_rerun") is False
assert summary.get("external_settlement_capture_preflight_decision") == "CAPTURE_INPUTS_BLOCKED"
assert summary.get("external_settlement_handoff_operator_command_entrypoints_missing") == 0
assert summary.get("external_settlement_handoff_operator_commands_with_shell_redirection_placeholders") == 0
assert summary.get("external_settlement_handoff_operator_command_shell_surface_ready") is True
assert summary.get("external_settlement_handoff_operator_sequence_ready") is True
assert summary.get("x0t_governance_execute_readiness_available") is True
assert summary.get("x0t_governance_execute_handoff_available") is True
assert summary.get("x0t_governance_execute_handoff_clear") is True
assert summary.get("x0t_governance_execute_handoff_actionable") is True
assert summary.get("x0t_governance_proposal_executed") is False
assert summary.get("x0t_governance_handoff_operator_command_entrypoints_missing") == 0
assert summary.get("x0t_governance_handoff_operator_commands_with_shell_redirection_placeholders") == 0
assert summary.get("x0t_governance_handoff_operator_command_shell_surface_ready") is True
assert summary.get("image_digests_can_close") is False
assert summary.get("image_digests_operator_handoff_decision") == "LIVE_ROLLOUT_IMAGE_DIGESTS_BLOCKED_ON_OPERATOR"
assert summary.get("image_digests_missing_inputs_total") == 1
assert summary.get("image_digests_operator_actions_total") == 5
assert summary.get("image_digests_operator_command_entrypoints_missing") == 0
assert summary.get("image_digests_operator_command_surface_ready") is True
assert summary.get("image_digests_operator_commands_with_shell_redirection_placeholders") == 0
assert summary.get("image_digests_operator_command_shell_surface_ready") is True
assert summary.get("semantic_blocking_items_total", 0) > 0
assert data.get("top_blockers")
blocker_statuses = {
    item.get("id"): item.get("status")
    for item in data.get("top_blockers", [])
    if isinstance(item, dict)
}
assert blocker_statuses.get("external_settlement:001") == "OPERATOR_INPUT_REQUIRED"
assert blocker_statuses.get("x0t-governance:proposal-execution") == "OPERATOR_APPROVAL_REQUIRED"
assert blocker_statuses.get("x0t-contract:deployment-config") == "OPERATOR_INPUT_REQUIRED"
assert blocker_statuses.get("live-rollout:image-digests") == "OPERATOR_INPUT_REQUIRED"
assert blocker_statuses.get("integration-spine:semantic-production-readiness") == "OPERATOR_INPUT_REQUIRED"
governance_blockers = [
    item for item in data.get("top_blockers", [])
    if isinstance(item, dict) and item.get("id") == "x0t-governance:proposal-execution"
]
assert governance_blockers
required_evidence = governance_blockers[0].get("required_evidence", [])
assert any(str(item).startswith("next executable after UTC: ") and str(item).strip() != "next executable after UTC:" for item in required_evidence)
handoffs = data.get("operator_handoffs", {})
assert handoffs.get("source_available") is True
assert handoffs.get("external_settlement", {}).get("operator_command_checks")
assert handoffs.get("x0t_governance_execute", {}).get("operator_command_checks")
assert handoffs.get("live_rollout_image_digests", {}).get("operator_command_checks")
PY
  then
    pass "integration-spine current evidence rollup current shards fail closed"
  else
    fail "integration-spine current evidence rollup current shards fail closed"
  fi
  rm -f "${tmp}"
}

run_rollout_provenance_current_smoke_check() {
  local output code
  output=".tmp/validation-shards/live-rollout-image-digests-closure-attempt-current.json"
  set +e
  python3 -m src.integration.rollout_provenance --root . --output-json "${output}" --require-ready >/dev/null 2>&1
  code=$?
  set -e
  if [[ "${code}" -eq 2 ]] && python3 - "${output}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
summary = data.get("summary", {})
assert data.get("status") == "VERIFIED HERE"
assert data.get("ok") is True
assert data.get("decision") == "CANNOT_CLOSE_WITH_CURRENT_RETAINED_ARTIFACTS"
assert data.get("operator_handoff_decision") == "LIVE_ROLLOUT_IMAGE_DIGESTS_BLOCKED_ON_OPERATOR"
assert data.get("ready_for_completion_rerun") is False
assert data.get("goal_can_be_marked_complete") is False
assert summary.get("can_close_image_digests_blocker") is False
assert summary.get("missing_inputs_total") == 1
assert summary.get("operator_actions_total") == 5
assert summary.get("operator_commands_total") == 4
assert summary.get("operator_command_entrypoints_missing") == 0
assert summary.get("operator_command_surface_ready") is True
assert summary.get("operator_commands_with_shell_redirection_placeholders") == 0
assert summary.get("operator_command_shell_surface_ready") is True
assert summary.get("raw_deploy_images_total", 0) > 0
assert summary.get("raw_deploy_images_digest_pinned", 0) < summary.get("raw_deploy_images_total", 0)
assert summary.get("collector_image_digest_preflight_errors", 0) > 0
assert summary.get("runtime_image_provenance_artifacts_retained_here") is False
assert data.get("blocking_preflight_errors")
missing = data.get("missing_inputs", [])
assert missing and missing[0].get("id") == "live_rollout_image_digest_provenance"
checks = {
    item.get("action_id"): item
    for item in data.get("operator_command_checks", [])
    if isinstance(item, dict)
}
for action_id in [
    "render_template_pack",
    "verify_live_rollout_evidence_gate",
    "rerun_rollout_provenance",
    "rerun_current_evidence_rollup",
]:
    assert checks.get(action_id, {}).get("entrypoint_exists") is True
PY
  then
    pass "integration-spine rollout provenance current shards fail closed"
  else
    fail "integration-spine rollout provenance current shards fail closed"
  fi
}

run_operator_bundle_identity_current_smoke_check() {
  local tmp code
  tmp="$(mktemp)"
  set +e
  python3 -m src.integration.operator_bundle_identity --root . --output-json "${tmp}" --require-clean >/dev/null 2>&1
  code=$?
  set -e
  if [[ "${code}" -eq 0 || "${code}" -eq 2 ]] && python3 - "${tmp}" "${code}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
code = int(sys.argv[2])
summary = data.get("summary", {})
assert data.get("status") == "VERIFIED HERE"
assert data.get("ok") is True
assert data.get("decision") in {"OPERATOR_BUNDLE_IDENTITY_FIX_REQUIRED", "OPERATOR_BUNDLE_IDENTITY_CLEAN"}
assert data.get("goal_can_be_marked_complete") is False
assert summary.get("files_total", 0) > 0
if code == 0:
    assert data.get("decision") == "OPERATOR_BUNDLE_IDENTITY_CLEAN"
    assert summary.get("files_needing_identity_update") == 0
    assert summary.get("manifest_identity_mismatches_total") == 0
    assert summary.get("clean") is True
else:
    assert data.get("decision") == "OPERATOR_BUNDLE_IDENTITY_FIX_REQUIRED"
    assert summary.get("files_needing_identity_update", 0) > 0
    assert summary.get("manifest_identity_mismatches_total", 0) > 0
    assert summary.get("clean") is False
PY
  then
    pass "integration-spine operator bundle identity current shards are safe"
  else
    fail "integration-spine operator bundle identity current shards are safe"
  fi
  rm -f "${tmp}"
}

run_operator_bundle_identity_patch_current_smoke_check() {
  local tmp
  tmp="$(mktemp)"
  if python3 scripts/ops/apply_operator_bundle_identity_patch.py --root . --output-json "${tmp}" >/dev/null 2>&1 \
    && python3 - "${tmp}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
summary = data.get("summary", {})
assert data.get("status") == "VERIFIED HERE"
assert data.get("ok") is True
assert data.get("decision") in {"IDENTITY_PATCH_DRY_RUN_READY", "IDENTITY_PATCH_NOT_NEEDED"}
assert data.get("goal_can_be_marked_complete") is False
assert data.get("apply_requested") is False
assert data.get("mutates_files") is False
assert data.get("mutates_files_outside_operator_bundle") is False
assert data.get("mutates_nl") is False
assert data.get("mutates_spb") is False
assert data.get("mutates_vpn_runtime") is False
assert data.get("materializes_evidence") is False
assert data.get("installs_raw_evidence") is False
assert data.get("promotes_production_ready") is False
assert data.get("changes_evidence_status") is False
assert summary.get("plan_entries_total", 0) >= 0
assert summary.get("unsafe_operations_total") == 0
PY
  then
    pass "integration-spine operator bundle identity patch dry-run is safe"
  else
    fail "integration-spine operator bundle identity patch dry-run is safe"
  fi
  rm -f "${tmp}"
}

run_replacement_passport_current_smoke_check() {
  local tmp verify_tmp code
  tmp="$(mktemp)"
  verify_tmp="$(mktemp)"
  set +e
  python3 -m src.integration.production_evidence_replacement_passport \
    --root . \
    --output-json "${tmp}" \
    --verification-output-json "${verify_tmp}" \
    --require-valid \
    --require-ready >/dev/null 2>&1
  code=$?
  set -e
  if [[ "${code}" -eq 2 ]] && python3 - "${tmp}" "${verify_tmp}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
verification = json.load(open(sys.argv[2], encoding="utf-8"))
summary = data.get("summary", {})
assert data.get("status") == "VERIFIED HERE"
assert data.get("ok") is True
assert data.get("decision") == "PRODUCTION_EVIDENCE_REPLACEMENT_PASSPORT_READY_FOR_OPERATOR"
assert data.get("production_ready") is False
assert data.get("goal_can_be_marked_complete") is False
assert summary.get("items_total") == 64
assert summary.get("items_blocking") == 64
assert summary.get("raw_evidence_items") == 63
assert summary.get("external_settlement_items") == 1
assert summary.get("required_evidence_files_total") == summary.get("items_total")
assert summary.get("required_evidence_files_ready", 0) < summary.get("required_evidence_files_total", 0)
assert summary.get("raw_operator_packet_files_total") == 63
assert summary.get("raw_operator_packet_files_covered_by_checklist") == 30
assert summary.get("raw_operator_packet_files_added_to_passport") == 33
assert summary.get("raw_operator_packet_files_production_ready") == 0
assert summary.get("raw_operator_packet_files_replacement_required") == 63
assert summary.get("raw_install_claim_source") == "return_acceptance"
assert summary.get("current_raw_files_installed") == 0
assert summary.get("coverage_raw_files_reported_installed") == 0
assert summary.get("return_acceptance_raw_files_staged") == 0
assert summary.get("return_acceptance_raw_files_local_observation", 0) > 0
assert verification.get("status") == "VERIFIED HERE"
assert verification.get("ok") is True
assert verification.get("valid") is True
assert verification.get("decision") == "VALID_PRODUCTION_EVIDENCE_REPLACEMENT_PASSPORT_READY_FOR_OPERATOR"
assert verification.get("summary", {}).get("checks_failed") == 0
PY
  then
    pass "integration-spine production evidence replacement passport fails closed"
  else
    fail "integration-spine production evidence replacement passport fails closed"
  fi
  rm -f "${tmp}" "${verify_tmp}"
}

run_production_evidence_import_current_smoke_check() {
  local import_tmp next_tmp code
  import_tmp="$(mktemp)"
  next_tmp="$(mktemp)"
  set +e
  python3 -m src.integration.production_evidence_import \
    --root . \
    --output-import-json "${import_tmp}" \
    --output-next-inputs-json "${next_tmp}" \
    --require-ready >/dev/null 2>&1
  code=$?
  set -e
  if [[ "${code}" -eq 2 ]] && python3 - "${import_tmp}" "${next_tmp}" <<'PY'
import json
import sys

import_report = json.load(open(sys.argv[1], encoding="utf-8"))
next_report = json.load(open(sys.argv[2], encoding="utf-8"))
import_summary = import_report.get("summary", {})
next_summary = next_report.get("summary", {})
assert import_report.get("status") == "VERIFIED HERE"
assert import_report.get("ok") is True
assert str(import_report.get("schema_version", "")).endswith("v2-repo-generated")
assert import_report.get("production_evidence_import_decision") == "BLOCKED_PRODUCTION_EVIDENCE"
assert import_report.get("goal_can_be_marked_complete") is False
assert import_report.get("materializes_evidence") is False
assert import_report.get("mutates_files") is False
assert import_report.get("mutates_vpn_runtime") is False
assert import_summary.get("required_evidence_keys_total") == 10
assert import_summary.get("source_artifacts_total") == 10
assert import_summary.get("source_artifacts_ready") == 0
assert import_summary.get("source_artifacts_pending") == 10
assert import_summary.get("source_artifact_files_total") == 64
assert import_summary.get("source_artifact_files_found") == 63
assert import_summary.get("production_evidence_complete") is False
assert len(import_report.get("source_results", [])) == 10
assert next_report.get("status") == "VERIFIED HERE"
assert next_report.get("ok") is True
assert str(next_report.get("schema_version", "")).endswith("v2-repo-generated")
assert next_report.get("decision") == "BLOCKED_PRODUCTION_INPUTS"
assert next_report.get("ready_for_production_closeout_review") is False
assert next_report.get("goal_can_be_marked_complete") is False
assert next_summary.get("required_inputs_total") == 10
assert next_summary.get("required_inputs_ready") == 0
assert next_summary.get("required_inputs_pending") == 10
assert next_summary.get("source_artifacts_total") == 10
assert len(next_report.get("required_inputs", [])) == 10
PY
  then
    pass "integration-spine production evidence import current shards fail closed"
  else
    fail "integration-spine production evidence import current shards fail closed"
  fi
  rm -f "${import_tmp}" "${next_tmp}"
}

run_required_evidence_consistency_current_smoke_check() {
  local tmp
  tmp="$(mktemp)"
  if python3 -m src.integration.required_evidence_consistency --root . --output-json "${tmp}" --require-valid >/dev/null 2>&1 \
    && python3 - "${tmp}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
summary = data.get("summary", {})
assert data.get("status") == "VERIFIED HERE"
assert data.get("ok") is True
assert data.get("valid") is True
assert data.get("decision") == "VALID_REQUIRED_EVIDENCE_CONSISTENCY_BLOCKED_ON_OPERATOR"
assert data.get("production_ready") is False
assert data.get("goal_can_be_marked_complete") is False
assert summary.get("errors_total") == 0
assert summary.get("sources_total") == 8
assert summary.get("required_evidence_files_total") == 64
assert summary.get("raw_required_evidence_files_total") == 63
assert summary.get("external_required_evidence_files_total") == 1
assert summary.get("packet_required_evidence_files_total") == summary.get("required_evidence_files_total")
assert summary.get("packet_passport_item_coverage_ready") is True
assert summary.get("raw_operator_packet_decision") == "RAW_EVIDENCE_OPERATOR_PACKET_ACTIONABLE"
assert summary.get("raw_operator_packet_local_handoff_complete") is True
assert summary.get("raw_operator_packet_production_ready") is False
assert summary.get("raw_operator_packet_files_total") == 63
assert summary.get("raw_operator_packet_files_production_ready") == 0
assert summary.get("raw_operator_packet_files_replacement_required") == 63
assert summary.get("raw_operator_packet_readiness_decision") == "BLOCKED_ON_OPERATOR_PRODUCTION_EVIDENCE"
assert summary.get("raw_operator_packet_readiness_ready_for_collectors") is False
assert summary.get("raw_operator_packet_readiness_collectors_ready") == 0
assert summary.get("raw_operator_packet_readiness_collectors_blocked") == 9
assert summary.get("raw_operator_packet_readiness_collectors_total") == 9
assert summary.get("raw_operator_packet_readiness_raw_files_ready") == 0
assert summary.get("raw_operator_packet_readiness_raw_files_local_observation") == 63
assert summary.get("raw_operator_packet_readiness_raw_files_total") == 63
assert summary.get("raw_operator_packet_paths_in_passport") == 63
assert summary.get("raw_operator_packet_paths_missing_from_passport") == 0
assert summary.get("rollup_evidence_files_total") == 64
assert summary.get("rollup_evidence_files_valid") == 0
assert summary.get("rollup_evidence_files_missing") == 1
assert summary.get("rollup_evidence_files_invalid") == 63
assert summary.get("rollup_evidence_files_operator_input_required") == 63
PY
  then
    pass "integration-spine required evidence consistency current shards are valid blocked"
  else
    fail "integration-spine required evidence consistency current shards are valid blocked"
  fi
  rm -f "${tmp}"
}

run_rollup_approval_contract_current_smoke_check() {
  local tmp code
  tmp="$(mktemp)"
  set +e
  python3 -m src.integration.rollup_approval_contract --root . --output-json "${tmp}" --require-ready >/dev/null 2>&1
  code=$?
  set -e
  if [[ "${code}" -eq 2 ]] && python3 - "${tmp}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
summary = data.get("summary", {})
assert data.get("status") == "VERIFIED HERE"
assert data.get("ok") is True
assert data.get("ready") is False
assert data.get("decision") == "ROLLUP_APPROVAL_BLOCKED_ON_OPERATOR_EVIDENCE"
assert data.get("goal_can_be_marked_complete") is False
assert summary.get("source_errors_total") == 0
assert summary.get("sources_total") == 13
assert summary.get("sources_blocking", 0) > 0
assert summary.get("evidence_files_total") == 64
assert summary.get("evidence_files_valid") == 0
assert summary.get("evidence_files_valid", 0) < summary.get("evidence_files_total", 0)
assert summary.get("evidence_files_missing") == 1
assert summary.get("evidence_files_invalid") == 63
assert summary.get("evidence_files_operator_input_required") == 63
sample_statuses = {
    item.get("status")
    for report in data.get("source_reports", [])
    if isinstance(report, dict)
    for item in report.get("evidence_files", [])
    if isinstance(item, dict)
}
assert "OPERATOR_INPUT_REQUIRED" in sample_statuses
PY
  then
    pass "integration-spine rollup approval contract current shards fail closed"
  else
    fail "integration-spine rollup approval contract current shards fail closed"
  fi
  rm -f "${tmp}"
}

run_production_input_return_acceptance_current_smoke_check() {
  local tmp code
  tmp="$(mktemp)"
  set +e
  python3 -m src.integration.production_input_return_acceptance --root . --output-json "${tmp}" --require-ready >/dev/null 2>&1
  code=$?
  set -e
  if [[ "${code}" -eq 2 ]] && python3 - "${tmp}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
summary = data.get("summary", {})
assert data.get("status") == "VERIFIED HERE"
assert data.get("ok") is True
assert data.get("decision") == "RETURN_ACCEPTANCE_BLOCKED_ON_OPERATOR_EVIDENCE"
assert data.get("acceptance_decision") == "RETURN_ACCEPTANCE_BLOCKED"
assert data.get("goal_can_be_marked_complete") is False
assert data.get("ready_for_pipeline_install") is False
assert summary.get("source_errors_total") == 0
assert summary.get("evidence_keys_total", 0) > 0
assert summary.get("raw_ready_to_stage") is False
assert summary.get("raw_files_local_observation", 0) > 0
assert summary.get("raw_files_ready_to_stage") == 0
assert summary.get("raw_files_staged") == 0
assert summary.get("external_settlement_live_rpc_ready") is False
assert summary.get("external_artifacts_operator_required", 0) > 0
PY
  then
    pass "integration-spine production input return acceptance current shards fail closed"
  else
    fail "integration-spine production input return acceptance current shards fail closed"
  fi
  rm -f "${tmp}"
}

run_production_input_bundle_stage_current_smoke_check() {
  local tmp code
  tmp="$(mktemp)"
  set +e
  python3 -m src.integration.production_input_bundle_stage --root . --output-json "${tmp}" --require-ready >/dev/null 2>&1
  code=$?
  set -e
  if [[ "${code}" -eq 2 ]] && python3 - "${tmp}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
summary = data.get("summary", {})
assert data.get("status") == "VERIFIED HERE"
assert data.get("ok") is True
assert str(data.get("schema_version", "")).endswith("v4-repo-generated")
assert "source-restored" not in str(data.get("schema_version", ""))
assert data.get("stage_decision") == "SCOPED_INPUT_BUNDLE_BLOCKED"
assert data.get("ready_to_stage") is False
assert data.get("goal_can_be_marked_complete") is False
assert data.get("mutates_files") is False
assert data.get("stages_operator_inputs") is False
assert summary.get("source_errors_total") == 0
assert summary.get("raw_install_claim_source") == "return_acceptance"
assert summary.get("raw_files_staged") == 0
assert summary.get("raw_files_already_staged") == 0
assert summary.get("raw_files_ready_to_stage") == 0
assert summary.get("pipeline_raw_files_installed") == 0
assert summary.get("raw_files_local_observation", 0) > 0
assert summary.get("raw_files_operator_required", 0) > 0
assert summary.get("external_settlement_live_rpc_ready") is False
assert summary.get("blocking_inputs_total", 0) > 0
assert summary.get("blocking_inputs_operator_input_required") == summary.get("blocking_inputs_total")
assert summary.get("blocking_inputs_generic_operator_required") == 0
assert {item.get("status") for item in data.get("blocking_inputs", [])} == {"OPERATOR_INPUT_REQUIRED"}
PY
  then
    pass "integration-spine production input bundle stage current shards fail closed"
  else
    fail "integration-spine production input bundle stage current shards fail closed"
  fi
  rm -f "${tmp}"
}

run_production_input_pipeline_current_smoke_check() {
  local tmp code
  tmp="$(mktemp)"
  set +e
  python3 -m src.integration.production_input_pipeline --root . --output-json "${tmp}" --require-ready >/dev/null 2>&1
  code=$?
  set -e
  if [[ "${code}" -eq 2 ]] && python3 - "${tmp}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
summary = data.get("summary", {})
assert data.get("status") == "VERIFIED HERE"
assert data.get("ok") is True
assert str(data.get("schema_version", "")).endswith("v4-repo-generated")
assert "source-restored" not in str(data.get("schema_version", ""))
assert data.get("pipeline_decision") == "PARTIAL_RAW_COLLECTOR_BLOCKED_ON_EVIDENCE"
assert data.get("goal_can_be_marked_complete") is False
assert data.get("ready") is False
assert summary.get("source_errors_total") == 0
assert summary.get("raw_files_install_claim_source") == "return_acceptance"
assert summary.get("raw_files_installed") == 0
assert summary.get("raw_files_staged") == 0
assert summary.get("raw_files_preflight_reported_installed") == 0
assert summary.get("raw_files_local_observation", 0) > 0
assert summary.get("external_settlement_live_rpc_ready") is False
assert summary.get("blocking_inputs_total", 0) > 0
assert summary.get("blocking_inputs_operator_input_required") == summary.get("blocking_inputs_total")
assert summary.get("blocking_inputs_generic_operator_required") == 0
assert summary.get("raw_install_operator_input_required", 0) > 0
assert summary.get("raw_install_generic_operator_required") == 0
blocked_install_statuses = {
    item.get("status")
    for item in data.get("raw_install_results", [])
    if item.get("ready_to_stage") is not True
}
assert blocked_install_statuses == {"OPERATOR_INPUT_REQUIRED"}
PY
  then
    pass "integration-spine production input pipeline current shards fail closed"
  else
    fail "integration-spine production input pipeline current shards fail closed"
  fi
  rm -f "${tmp}"
}

run_production_raw_evidence_readiness_current_smoke_check() {
  local tmp code
  tmp="$(mktemp)"
  set +e
  python3 -m src.integration.production_raw_evidence_readiness --root . --output-json "${tmp}" --require-ready >/dev/null 2>&1
  code=$?
  set -e
  if [[ "${code}" -eq 2 ]] && python3 - "${tmp}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
summary = data.get("summary", {})
assert data.get("status") == "VERIFIED HERE"
assert data.get("ok") is True
assert str(data.get("schema_version", "")).endswith("v2-repo-generated")
assert "source-restored" not in str(data.get("schema_version", ""))
assert data.get("raw_evidence_readiness_decision") == "BLOCKED_ON_OPERATOR_PRODUCTION_EVIDENCE"
assert data.get("ready_for_collectors") is False
assert data.get("goal_can_be_marked_complete") is False
assert data.get("mutates_files") is False
assert data.get("mutates_vpn_runtime") is False
assert summary.get("collectors_ready") == 0
assert summary.get("collectors_blocked", 0) > 0
assert summary.get("raw_files_ready") == 0
assert summary.get("raw_files_total", 0) > 0
assert summary.get("raw_files_local_observation", 0) > 0
assert summary.get("raw_files_conflicting_status_fields") == 0
assert summary.get("raw_files_placeholder_source_commands") == 0
assert summary.get("raw_files_placeholder_values") == 0
PY
  then
    pass "production raw evidence readiness current shards fail closed"
  else
    fail "production raw evidence readiness current shards fail closed"
  fi
  rm -f "${tmp}"
}

run_production_raw_evidence_semantics_current_smoke_check() {
  local tmp code
  tmp="$(mktemp)"
  set +e
  python3 -m src.integration.production_raw_evidence_semantics --root . --output-json "${tmp}" --require-ready >/dev/null 2>&1
  code=$?
  set -e
  if [[ "${code}" -eq 2 ]] && python3 - "${tmp}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
summary = data.get("summary", {})
assert data.get("status") == "VERIFIED HERE"
assert data.get("ok") is True
assert str(data.get("schema_version", "")).endswith("v2-repo-generated")
assert "source-restored" not in str(data.get("schema_version", ""))
assert data.get("semantic_readiness_decision") == "BLOCKED_RAW_INPUTS"
assert data.get("raw_evidence_readiness_decision") == "BLOCKED_ON_OPERATOR_PRODUCTION_EVIDENCE"
assert data.get("runs_semantic_collectors") is False
assert data.get("materializes_evidence") is False
assert data.get("mutates_files") is False
assert data.get("mutates_vpn_runtime") is False
assert data.get("goal_can_be_marked_complete") is False
assert summary.get("collectors_total", 0) > 0
assert summary.get("collectors_ready") == 0
assert summary.get("raw_files_total", 0) > 0
assert summary.get("raw_files_ready") == 0
assert summary.get("raw_files_missing") == 0
assert summary.get("raw_files_local_observation", 0) > 0
assert summary.get("raw_files_conflicting_status_fields") == 0
assert summary.get("raw_files_placeholder_source_commands") == 0
assert summary.get("raw_files_placeholder_values") == 0
assert summary.get("semantic_collectors_run") == 0
assert summary.get("bundle_writes") == 0
PY
  then
    pass "production raw evidence semantics current shards fail closed"
  else
    fail "production raw evidence semantics current shards fail closed"
  fi
  rm -f "${tmp}"
}

run_production_raw_evidence_pipeline_current_smoke_check() {
  local tmp code
  tmp="$(mktemp)"
  set +e
  python3 -m src.integration.production_raw_evidence_pipeline --root . --output-json "${tmp}" --require-ready >/dev/null 2>&1
  code=$?
  set -e
  if [[ "${code}" -eq 2 ]] && python3 - "${tmp}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
summary = data.get("summary", {})
assert data.get("status") == "VERIFIED HERE"
assert data.get("ok") is True
assert str(data.get("schema_version", "")).endswith("v2-repo-generated")
assert "source-restored" not in str(data.get("schema_version", ""))
assert data.get("pipeline_decision") == "BLOCKED_RAW_INPUTS"
assert data.get("ready_for_collector_execution") is False
assert data.get("goal_can_be_marked_complete") is False
assert data.get("execution_performed") is False
assert data.get("runs_collectors") is False
assert data.get("runs_evidence_gates") is False
assert data.get("mutates_files") is False
assert summary.get("planned_steps_total", 0) > 0
assert summary.get("missing_entrypoints") == 0
assert summary.get("collectors_ready") == 0
assert summary.get("collectors_blocked", 0) > 0
assert summary.get("raw_files_ready") == 0
assert summary.get("raw_files_total", 0) > 0
assert summary.get("raw_files_local_observation", 0) > 0
assert summary.get("raw_files_conflicting_status_fields") == 0
assert summary.get("raw_files_placeholder_source_commands") == 0
assert summary.get("raw_files_placeholder_values") == 0
PY
  then
    pass "production raw evidence pipeline current shards fail closed"
  else
    fail "production raw evidence pipeline current shards fail closed"
  fi
  rm -f "${tmp}"
}

run_production_raw_evidence_operator_packet_current_smoke_check() {
  local tmp
  tmp="$(mktemp)"
  if python3 -m src.integration.production_raw_evidence_operator_packet --root . --output-json "${tmp}" --require-actionable >/dev/null 2>&1 \
    && python3 - "${tmp}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
summary = data.get("summary", {})
assert data.get("status") == "VERIFIED HERE"
assert data.get("ok") is True
assert str(data.get("schema_version", "")).endswith("v1-repo-generated")
assert data.get("decision") == "RAW_EVIDENCE_OPERATOR_PACKET_ACTIONABLE"
assert data.get("local_handoff_complete") is True
assert data.get("production_ready") is False
assert data.get("goal_can_be_marked_complete") is False
assert summary.get("packets_total") == 9
assert summary.get("actionable_packets") == 9
assert summary.get("local_entrypoints_missing") == 0
assert summary.get("raw_files_total") == 63
assert summary.get("operator_bundle_files_existing") == 63
assert summary.get("operator_bundle_files_production_ready") == 0
assert summary.get("operator_bundle_files_replacement_required") == 63
assert summary.get("raw_readiness_decision") == "BLOCKED_ON_OPERATOR_PRODUCTION_EVIDENCE"
assert summary.get("raw_readiness_ready_for_collectors") is False
assert summary.get("raw_readiness_collectors_ready") == 0
assert summary.get("raw_readiness_collectors_blocked") == 9
assert summary.get("raw_readiness_collectors_total") == 9
assert summary.get("raw_readiness_raw_files_ready") == 0
assert summary.get("raw_readiness_raw_files_local_observation") == 63
assert summary.get("raw_readiness_raw_files_total") == 63
PY
  then
    pass "production raw evidence operator packet index is complete but not production-ready"
  else
    fail "production raw evidence operator packet index is complete but not production-ready"
  fi
  rm -f "${tmp}"
}

run_production_grade_goal_audit_current_smoke_check() {
  local tmp code
  tmp="$(mktemp)"
  set +e
  python3 scripts/ops/audit_production_grade_goal.py --root . --output-json "${tmp}" --output text --require-complete >/dev/null 2>&1
  code=$?
  set -e
  if [[ "${code}" -eq 2 ]] && python3 - "${tmp}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
summary = data.get("summary", {})
assert data.get("status") == "VERIFIED HERE"
assert data.get("ok") is True
assert str(data.get("schema_version", "")).endswith("v2-repo-generated")
assert data.get("completion_decision") == "NOT_COMPLETE"
assert data.get("goal_can_be_marked_complete") is False
assert summary.get("requirements_total") == 8
assert summary.get("requirements_missing_artifacts") == 0
assert summary.get("requirements_with_all_artifacts") == 8
assert summary.get("requirements_with_failed_artifact_checks") == 0
assert summary.get("requirements_with_production_gaps") == 8
assert len(summary.get("production_gap_requirement_ids", [])) == 8
assert summary.get("next_actions_total") == 5
assert summary.get("next_actions_operator_input_required") == 3
assert summary.get("next_actions_operator_approval_required") == 1
assert summary.get("next_actions_after_blockers") == 1
assert summary.get("next_actions_generic_blocking") == 0
assert summary.get("completion_gate_runner_available") is True
assert summary.get("completion_gate_runner_decision") == "NOT_COMPLETE"
assert summary.get("completion_gate_production_input_return_packet_available") is True
assert summary.get("completion_gate_production_input_return_packet_decision") == "RETURN_PACKET_BLOCKED_ON_OPERATOR_EVIDENCE"
assert summary.get("completion_gate_production_input_return_packet_blocking_inputs_total") == 31
assert summary.get("completion_gate_production_input_return_packet_blocking_raw_inputs") == 30
assert summary.get("completion_gate_production_input_return_packet_blocking_external_inputs") == 1
assert summary.get("completion_gate_production_input_return_packet_blocking_inputs_operator_input_required") == 31
assert summary.get("completion_gate_production_input_return_packet_blocking_inputs_generic_operator_required") == 0
assert summary.get("completion_gate_production_input_return_packet_operator_next_actions_total") == 2
assert summary.get("completion_gate_production_input_return_packet_operator_next_actions_operator_input_required") == 2
assert summary.get("completion_gate_production_input_return_packet_operator_next_actions_generic_blocking") == 0
assert summary.get("completion_gate_production_input_return_packet_raw_files_expected") == 63
assert summary.get("completion_gate_production_input_return_packet_raw_files_missing") == 33
assert summary.get("completion_gate_production_input_return_packet_raw_files_local_observation") == 30
assert summary.get("completion_gate_x0t_contract_handoff_decision") == "X0T_CONTRACT_DEPLOYMENT_CONFIG_BLOCKED_ON_OPERATOR"
assert summary.get("completion_gate_x0t_contract_handoff_approval_value_required") == "apply-bridge-address-base-sepolia"
assert summary.get("completion_gate_x0t_contract_handoff_missing_inputs_total") == 1
assert summary.get("completion_gate_x0t_contract_handoff_operator_actions_total") == 6
assert summary.get("completion_gate_x0t_contract_handoff_operator_approval_required_actions_total") == 1
assert summary.get("completion_gate_x0t_contract_handoff_operator_commands_total") == 5
assert summary.get("completion_gate_x0t_contract_handoff_operator_command_shell_surface_ready") is True
assert summary.get("completion_gate_x0t_contract_handoff_operator_commands_with_shell_redirection_placeholders") == 0
assert summary.get("completion_gate_x0t_contract_handoff_operator_sequence_ready") is True
assert summary.get("completion_gate_live_rollout_handoff_decision") == "LIVE_ROLLOUT_IMAGE_DIGESTS_BLOCKED_ON_OPERATOR"
assert summary.get("completion_gate_live_rollout_handoff_missing_inputs_total") == 1
assert summary.get("completion_gate_live_rollout_handoff_operator_actions_total") == 5
assert summary.get("completion_gate_live_rollout_handoff_operator_input_required_actions_total") == 2
assert summary.get("completion_gate_live_rollout_handoff_operator_commands_total") == 4
assert summary.get("completion_gate_live_rollout_handoff_operator_command_shell_surface_ready") is True
assert summary.get("completion_gate_live_rollout_handoff_operator_commands_with_shell_redirection_placeholders") == 0
assert summary.get("completion_gate_live_rollout_handoff_operator_sequence_ready") is True
actions = {
    item.get("id"): item.get("status")
    for item in data.get("next_actions", [])
    if isinstance(item, dict)
}
assert actions.get("replace_operator_evidence") == "OPERATOR_INPUT_REQUIRED"
assert actions.get("provide_x0t_bridge_contract_address") == "OPERATOR_INPUT_REQUIRED"
assert actions.get("apply_x0t_bridge_contract_address_with_approval") == "OPERATOR_APPROVAL_REQUIRED"
assert actions.get("return_live_rollout_image_digest_provenance") == "OPERATOR_INPUT_REQUIRED"
assert actions.get("rerun_production_closeout") == "AFTER_BLOCKERS"
PY
  then
    pass "production-grade goal audit current shards fail closed"
  else
    fail "production-grade goal audit current shards fail closed"
  fi
  rm -f "${tmp}"
}

run_objective_coverage_audit_current_smoke_check() {
  local tmp code
  tmp="$(mktemp)"
  set +e
  python3 -m src.integration.objective_coverage_audit --root . --output-json "${tmp}" --require-complete >/dev/null 2>&1
  code=$?
  set -e
  if [[ "${code}" -eq 2 ]] && python3 - "${tmp}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
summary = data.get("summary", {})
assert data.get("status") == "VERIFIED HERE"
assert data.get("ok") is True
assert str(data.get("schema_version", "")).endswith("v4-repo-generated")
assert "source-restored" not in str(data.get("schema_version", ""))
assert data.get("completion_decision") == "NOT_COMPLETE"
assert data.get("goal_can_be_marked_complete") is False
assert data.get("local_integration_ready") is True
assert data.get("production_ready") is False
assert summary.get("artifact_errors_total") == 0
assert summary.get("current_raw_files_installed") == 0
assert summary.get("raw_install_claim_source") == "return_acceptance"
assert summary.get("pipeline_raw_files_reported_installed") == 0
assert summary.get("return_acceptance_raw_files_staged") == 0
assert summary.get("return_acceptance_raw_files_local_observation", 0) > 0
assert summary.get("raw_inventory_files_total", 0) > 0
assert summary.get("raw_inventory_usable_for_goal_completion") == 0
assert summary.get("coverage_rows_total") == 32
assert summary.get("coverage_rows_blocking", 0) > 0
assert summary.get("required_goal_audit_rows_total") == 18
assert summary.get("required_goal_audit_rows_missing") == []
assert summary.get("raw_operator_packet_files_total") == 63
assert summary.get("raw_operator_packet_files_production_ready") == 0
assert summary.get("raw_operator_packet_files_replacement_required") == 63
assert summary.get("raw_operator_packet_readiness_decision") == "BLOCKED_ON_OPERATOR_PRODUCTION_EVIDENCE"
assert summary.get("raw_operator_packet_readiness_ready_for_collectors") is False
assert summary.get("raw_operator_packet_readiness_collectors_ready") == 0
assert summary.get("raw_operator_packet_readiness_collectors_blocked") == 9
assert summary.get("raw_operator_packet_readiness_collectors_total") == 9
assert summary.get("raw_operator_packet_readiness_raw_files_ready") == 0
assert summary.get("raw_operator_packet_readiness_raw_files_local_observation") == 63
assert summary.get("raw_operator_packet_readiness_raw_files_total") == 63
assert summary.get("external_settlement_handoff_available") is True
assert summary.get("external_settlement_handoff_clear") is True
assert summary.get("external_settlement_handoff_decision") == "X0T_EXTERNAL_SETTLEMENT_HANDOFF_BLOCKED_ON_OPERATOR"
assert summary.get("external_settlement_handoff_ready_for_completion_rerun") is False
assert summary.get("external_settlement_capture_preflight_decision") == "CAPTURE_INPUTS_BLOCKED"
assert summary.get("external_settlement_handoff_source_errors_total") == 0
assert summary.get("external_settlement_handoff_missing_inputs_total") == 5
assert summary.get("external_settlement_handoff_operator_actions_total") == 6
assert summary.get("external_settlement_handoff_operator_commands_total") == 5
assert summary.get("external_settlement_handoff_operator_command_entrypoints_missing") == 0
assert summary.get("external_settlement_handoff_operator_command_surface_ready") is True
assert summary.get("external_settlement_handoff_operator_commands_with_shell_redirection_placeholders") == 0
assert summary.get("external_settlement_handoff_operator_command_shell_surface_ready") is True
assert summary.get("closeout_operator_handoff_source_available") is True
assert summary.get("closeout_operator_handoff_source_errors_total") == 0
assert summary.get("closeout_x0t_governance_handoff_operator_actions_total") == 5
assert summary.get("closeout_x0t_governance_handoff_operator_commands_total") == 5
assert summary.get("closeout_x0t_governance_handoff_operator_sequence_ready") is True
assert summary.get("closeout_external_settlement_handoff_operator_actions_total") == 6
assert summary.get("closeout_external_settlement_handoff_operator_commands_total") == 5
assert summary.get("closeout_external_settlement_handoff_operator_sequence_ready") is True
assert summary.get("closeout_x0t_contract_handoff_available") is True
assert summary.get("closeout_x0t_contract_handoff_decision") == "X0T_CONTRACT_DEPLOYMENT_CONFIG_BLOCKED_ON_OPERATOR"
assert summary.get("closeout_x0t_contract_handoff_deployment_ready") is False
assert summary.get("closeout_x0t_contract_handoff_operator_actions_total") == 6
assert summary.get("closeout_x0t_contract_handoff_operator_commands_total") == 5
assert summary.get("closeout_x0t_contract_handoff_operator_sequence_ready") is True
assert summary.get("closeout_live_rollout_handoff_available") is True
assert summary.get("closeout_live_rollout_handoff_decision") == "LIVE_ROLLOUT_IMAGE_DIGESTS_BLOCKED_ON_OPERATOR"
assert summary.get("closeout_live_rollout_handoff_ready_for_completion_rerun") is False
assert summary.get("closeout_live_rollout_handoff_operator_actions_total") == 5
assert summary.get("closeout_live_rollout_handoff_operator_commands_total") == 4
assert summary.get("closeout_live_rollout_handoff_operator_command_entrypoints_missing") == 0
assert summary.get("closeout_live_rollout_handoff_operator_sequence_ready") is True
assert summary.get("production_grade_goal_audit_available") is True
assert summary.get("production_grade_goal_decision") == "NOT_COMPLETE"
assert summary.get("production_grade_goal_can_be_marked_complete") is False
assert summary.get("production_grade_next_actions_total") == 5
assert summary.get("production_grade_next_actions_operator_input_required") == 3
assert summary.get("production_grade_next_actions_operator_approval_required") == 1
assert summary.get("production_grade_next_actions_after_blockers") == 1
assert summary.get("production_grade_next_actions_generic_blocking") == 0
assert summary.get("production_grade_completion_gate_runner_available") is True
assert summary.get("production_grade_completion_gate_runner_decision") == "NOT_COMPLETE"
assert summary.get("production_grade_completion_gate_production_input_return_packet_available") is True
assert summary.get("production_grade_completion_gate_production_input_return_packet_decision") == "RETURN_PACKET_BLOCKED_ON_OPERATOR_EVIDENCE"
assert summary.get("production_grade_completion_gate_production_input_return_packet_blocking_inputs_total") == 31
assert summary.get("production_grade_completion_gate_production_input_return_packet_blocking_raw_inputs") == 30
assert summary.get("production_grade_completion_gate_production_input_return_packet_blocking_external_inputs") == 1
assert summary.get("production_grade_completion_gate_production_input_return_packet_blocking_inputs_operator_input_required") == 31
assert summary.get("production_grade_completion_gate_production_input_return_packet_blocking_inputs_generic_operator_required") == 0
assert summary.get("production_grade_completion_gate_production_input_return_packet_operator_next_actions_total") == 2
assert summary.get("production_grade_completion_gate_production_input_return_packet_operator_next_actions_operator_input_required") == 2
assert summary.get("production_grade_completion_gate_production_input_return_packet_operator_next_actions_generic_blocking") == 0
assert summary.get("production_grade_completion_gate_production_input_return_packet_raw_files_expected") == 63
assert summary.get("production_grade_completion_gate_production_input_return_packet_raw_files_missing") == 33
assert summary.get("production_grade_completion_gate_production_input_return_packet_raw_files_local_observation") == 30
assert summary.get("production_grade_completion_gate_x0t_contract_handoff_decision") == "X0T_CONTRACT_DEPLOYMENT_CONFIG_BLOCKED_ON_OPERATOR"
assert summary.get("production_grade_completion_gate_x0t_contract_handoff_approval_value_required") == "apply-bridge-address-base-sepolia"
assert summary.get("production_grade_completion_gate_x0t_contract_handoff_missing_inputs_total") == 1
assert summary.get("production_grade_completion_gate_x0t_contract_handoff_operator_actions_total") == 6
assert summary.get("production_grade_completion_gate_x0t_contract_handoff_operator_approval_required_actions_total") == 1
assert summary.get("production_grade_completion_gate_x0t_contract_handoff_operator_commands_total") == 5
assert summary.get("production_grade_completion_gate_x0t_contract_handoff_operator_command_shell_surface_ready") is True
assert summary.get("production_grade_completion_gate_x0t_contract_handoff_operator_commands_with_shell_redirection_placeholders") == 0
assert summary.get("production_grade_completion_gate_x0t_contract_handoff_operator_sequence_ready") is True
assert summary.get("production_grade_completion_gate_live_rollout_handoff_decision") == "LIVE_ROLLOUT_IMAGE_DIGESTS_BLOCKED_ON_OPERATOR"
assert summary.get("production_grade_completion_gate_live_rollout_handoff_missing_inputs_total") == 1
assert summary.get("production_grade_completion_gate_live_rollout_handoff_operator_actions_total") == 5
assert summary.get("production_grade_completion_gate_live_rollout_handoff_operator_input_required_actions_total") == 2
assert summary.get("production_grade_completion_gate_live_rollout_handoff_operator_commands_total") == 4
assert summary.get("production_grade_completion_gate_live_rollout_handoff_operator_command_shell_surface_ready") is True
assert summary.get("production_grade_completion_gate_live_rollout_handoff_operator_commands_with_shell_redirection_placeholders") == 0
assert summary.get("production_grade_completion_gate_live_rollout_handoff_operator_sequence_ready") is True
assert summary.get("x0t_governance_execute_readiness_available") is True
assert summary.get("x0t_governance_execute_decision") in {
    "NOT_READY_TIMELOCK_ACTIVE",
    "QUEUED_STATE_AFTER_TIMELOCK_CHECK_REQUIRED",
    "READY_TO_EXECUTE",
    "ALREADY_EXECUTED",
}
assert summary.get("x0t_governance_execute_handoff_available") is True
assert summary.get("x0t_governance_execute_handoff_clear") is True
assert summary.get("x0t_governance_execute_handoff_actionable") is True
assert isinstance(summary.get("x0t_governance_proposal_executed"), bool)
assert summary.get("x0t_governance_execute_handoff_operator_actions_total") == 5
assert summary.get("x0t_governance_execute_handoff_operator_commands_total") == 5
assert summary.get("x0t_governance_execute_handoff_operator_command_entrypoints_missing") == 0
assert summary.get("x0t_governance_execute_handoff_operator_command_surface_ready") is True
assert summary.get("x0t_governance_execute_handoff_operator_commands_with_shell_redirection_placeholders") == 0
assert summary.get("x0t_governance_execute_handoff_operator_command_shell_surface_ready") is True
assert summary.get("x0t_governance_execute_handoff_operator_sequence_ready") is True
assert "goal_audit:production_raw_evidence_operator_packet" in summary.get("blocking_row_ids", [])
rows = {
    row.get("id"): row
    for row in data.get("prompt_to_artifact_checklist", [])
    if isinstance(row, dict)
}
handoff_row = rows.get("external_settlement_operator_handoff", {})
assert ".tmp/validation-shards/x0t-external-settlement-operator-handoff-current.json" in handoff_row.get("artifact_paths", [])
assert handoff_row.get("local_ready") is True
assert handoff_row.get("production_ready") is False
handoff_evidence = handoff_row.get("evidence", {})
assert handoff_evidence.get("handoff_decision") == "X0T_EXTERNAL_SETTLEMENT_HANDOFF_BLOCKED_ON_OPERATOR"
assert handoff_evidence.get("ready_for_completion_rerun") is False
assert handoff_evidence.get("operator_command_entrypoints_missing") == 0
assert handoff_evidence.get("operator_commands_with_shell_redirection_placeholders") == 0
assert handoff_evidence.get("operator_command_shell_surface_ready") is True
governance_handoff_row = rows.get("x0t_governance_execute_handoff", {})
assert ".tmp/validation-shards/x0t-governance-execute-operator-handoff-current.json" in governance_handoff_row.get("artifact_paths", [])
assert governance_handoff_row.get("local_ready") is True
assert governance_handoff_row.get("production_ready") is False
governance_handoff_evidence = governance_handoff_row.get("evidence", {})
assert governance_handoff_evidence.get("handoff_decision") in {
    "X0T_GOVERNANCE_EXECUTE_HANDOFF_BLOCKED_ON_READINESS",
    "X0T_GOVERNANCE_EXECUTE_HANDOFF_READY_FOR_OPERATOR_APPROVAL",
    "X0T_GOVERNANCE_EXECUTE_HANDOFF_ALREADY_EXECUTED",
}
assert governance_handoff_evidence.get("handoff_actionable") is True
assert governance_handoff_evidence.get("operator_commands_total") == 5
assert governance_handoff_evidence.get("operator_command_entrypoints_missing") == 0
assert governance_handoff_evidence.get("operator_commands_with_shell_redirection_placeholders") == 0
assert governance_handoff_evidence.get("operator_command_shell_surface_ready") is True
assert governance_handoff_evidence.get("operator_sequence_ready") is True
next_actions = {
    item.get("id"): item
    for item in data.get("next_actions", [])
    if isinstance(item, dict)
}
external_action = next_actions.get("submit_external_settlement_receipt", {})
if summary.get("current_external_settlement_ready") is True:
    assert external_action.get("status") == "DONE"
elif summary.get("external_settlement_handoff_clear") is True:
    assert external_action.get("status") == "OPERATOR_INPUT_REQUIRED"
else:
    assert external_action.get("status") == "BLOCKING"
if summary.get("current_external_settlement_ready") is not True:
    assert external_action.get("handoff_decision") == "X0T_EXTERNAL_SETTLEMENT_HANDOFF_BLOCKED_ON_OPERATOR"
    assert external_action.get("ready_for_completion_rerun") is False
    assert external_action.get("capture_inputs_ready") is False
raw_action = next_actions.get("replace_semantically_blocked_raw_evidence", {})
if summary.get("raw_inventory_usable_for_goal_completion") == summary.get("raw_inventory_files_total"):
    assert raw_action.get("status") == "DONE"
elif (
    summary.get("raw_operator_packet_readiness_decision") == "BLOCKED_ON_OPERATOR_PRODUCTION_EVIDENCE"
    and (summary.get("raw_operator_packet_files_replacement_required") or 0) > 0
):
    assert raw_action.get("status") == "OPERATOR_INPUT_REQUIRED"
    assert raw_action.get("raw_operator_packet_decision") == "RAW_EVIDENCE_OPERATOR_PACKET_ACTIONABLE"
    assert raw_action.get("raw_operator_packet_local_handoff_complete") is True
    assert raw_action.get("raw_operator_packet_files_replacement_required") == summary.get(
        "raw_operator_packet_files_replacement_required"
    )
    assert raw_action.get("raw_operator_packet_readiness_decision") == "BLOCKED_ON_OPERATOR_PRODUCTION_EVIDENCE"
    assert raw_action.get("raw_operator_packet_readiness_raw_files_local_observation") == summary.get(
        "raw_operator_packet_readiness_raw_files_local_observation"
    )
else:
    assert raw_action.get("status") == "BLOCKING"
governance_action = next_actions.get("execute_x0t_governance_proposal_after_timelock", {})
if summary.get("x0t_governance_proposal_executed") is True:
    assert governance_action.get("status") == "DONE"
elif summary.get("x0t_governance_ready_for_operator_execute") is True:
    assert governance_action.get("status") == "OPERATOR_APPROVAL_REQUIRED"
else:
    assert governance_action.get("status") == "BLOCKING"
assert governance_action.get("readiness_decision") in {
    "NOT_READY_TIMELOCK_ACTIVE",
    "QUEUED_STATE_AFTER_TIMELOCK_CHECK_REQUIRED",
    "READY_TO_EXECUTE",
    "ALREADY_EXECUTED",
}
assert governance_action.get("requires_operator_approval") is True
assert governance_action.get("submits_transaction") is True
assert governance_action.get("approval_value_required") == "execute-proposal-1-base-sepolia"
commands = governance_action.get("commands", [])
assert "python3 scripts/ops/check_x0t_governance_execute_readiness.py --write-json --write-md --require-ready" in commands
assert "python3 execute_dao_proposal.py --dry-run" in commands
assert (
    "X0T_EXECUTE_PROPOSAL_APPROVAL=execute-proposal-1-base-sepolia "
    "PRIVATE_KEY=\"$PRIVATE_KEY\" python3 execute_dao_proposal.py"
) in commands
assert governance_action.get("required_artifact") == ".tmp/validation-shards/x0t-governance-execute-proposal-1-receipt-current.json"
assert next_actions.get("provide_x0t_bridge_contract_address", {}).get("status") == "OPERATOR_INPUT_REQUIRED"
bridge_apply_action = next_actions.get("apply_x0t_bridge_contract_address_with_approval", {})
assert bridge_apply_action.get("status") == "OPERATOR_APPROVAL_REQUIRED"
assert bridge_apply_action.get("approval_value_required") == "apply-bridge-address-base-sepolia"
assert next_actions.get("return_live_rollout_image_digest_provenance", {}).get("status") == "OPERATOR_INPUT_REQUIRED"
assert next_actions.get("rerun_production_closeout", {}).get("status") == "AFTER_BLOCKERS"
closeout_row = rows.get("production_closeout_review", {})
closeout_summary = closeout_row.get("evidence", {}).get("summary", {})
assert closeout_summary.get("operator_handoff_source_available") is True
assert closeout_summary.get("x0t_governance_handoff_operator_sequence_ready") is True
assert closeout_summary.get("external_settlement_handoff_operator_sequence_ready") is True
assert closeout_summary.get("x0t_contract_handoff_operator_sequence_ready") is True
assert closeout_summary.get("live_rollout_handoff_operator_sequence_ready") is True
PY
  then
    pass "integration-spine objective coverage audit current shards fail closed"
  else
    fail "integration-spine objective coverage audit current shards fail closed"
  fi
  rm -f "${tmp}"
}

run_goal_completion_audit_current_smoke_check() {
  local tmp code
  tmp="$(mktemp)"
  set +e
  python3 -m src.integration.goal_completion_audit --root . --output-json "${tmp}" --require-complete >/dev/null 2>&1
  code=$?
  set -e
  if [[ "${code}" -eq 2 ]] && python3 - "${tmp}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
summary = data.get("summary", {})
assert data.get("status") == "VERIFIED HERE"
assert data.get("ok") is True
assert data.get("schema_version") == "x0tta6bl4-integration-spine-goal-completion-audit-v2-repo-generated"
assert data.get("source_schema_version") == "x0tta6bl4-integration-spine-objective-coverage-audit-v4-repo-generated"
assert data.get("compatibility_alias_for") == "integration-spine-objective-coverage-audit-current"
assert data.get("completion_decision") == "NOT_COMPLETE"
assert data.get("goal_can_be_marked_complete") is False
assert data.get("local_integration_ready") is True
assert data.get("production_ready") is False
assert summary.get("artifact_errors_total") == 0
assert summary.get("coverage_rows_total") == 32
assert summary.get("coverage_rows_blocking", 0) > 0
assert summary.get("required_goal_audit_rows_total") == 18
assert summary.get("required_goal_audit_rows_missing") == []
assert summary.get("production_grade_next_actions_total") == 5
assert summary.get("production_grade_next_actions_operator_approval_required") == 1
assert summary.get("production_grade_completion_gate_production_input_return_packet_blocking_raw_inputs") == 30
assert summary.get("production_grade_completion_gate_production_input_return_packet_operator_next_actions_total") == 2
next_action_statuses = {
    item.get("status")
    for item in data.get("next_actions", [])
    if isinstance(item, dict)
}
assert "OPERATOR_INPUT_REQUIRED" in next_action_statuses
assert "OPERATOR_APPROVAL_REQUIRED" in next_action_statuses
assert "BLOCKING" not in next_action_statuses
next_actions = {
    item.get("id"): item
    for item in data.get("next_actions", [])
    if isinstance(item, dict)
}
assert next_actions.get("apply_x0t_bridge_contract_address_with_approval", {}).get("status") == "OPERATOR_APPROVAL_REQUIRED"
assert next_actions.get("return_live_rollout_image_digest_provenance", {}).get("status") == "OPERATOR_INPUT_REQUIRED"
row_statuses = {
    item.get("status")
    for item in data.get("prompt_to_artifact_checklist", [])
    if isinstance(item, dict)
}
assert "BLOCKING" not in row_statuses
PY
  then
    pass "integration-spine goal completion audit current shards fail closed"
  else
    fail "integration-spine goal completion audit current shards fail closed"
  fi
  rm -f "${tmp}"
}

run_completion_gate_runner_current_smoke_check() {
  local tmp code
  tmp="$(mktemp)"
  set +e
  python3 -m src.integration.completion_gate_runner --root . --output-json "${tmp}" --require-complete >/dev/null 2>&1
  code=$?
  set -e
  if [[ "${code}" -eq 2 ]] && python3 - "${tmp}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
summary = data.get("summary", {})
assert data.get("status") == "VERIFIED HERE"
assert data.get("ok") is True
assert str(data.get("schema_version", "")).endswith("v5-repo-generated")
assert "source-restored" not in str(data.get("schema_version", ""))
assert data.get("completion_decision") == "NOT_COMPLETE"
assert data.get("goal_can_be_marked_complete") is False
assert summary.get("steps_total", 0) > 0
assert summary.get("steps_blocked_expected", 0) > 0
assert summary.get("steps_failed_unexpected") == 0
assert summary.get("raw_install_claim_source") == "return_acceptance"
assert summary.get("current_raw_files_installed") == 0
assert summary.get("pipeline_raw_files_reported_installed") == 0
assert summary.get("coverage_raw_files_reported_installed") == 0
assert summary.get("production_input_return_packet_available") is True
assert summary.get("production_input_return_packet_decision") == "RETURN_PACKET_BLOCKED_ON_OPERATOR_EVIDENCE"
assert summary.get("production_input_return_packet_blocking_inputs_total") == 31
assert summary.get("production_input_return_packet_blocking_raw_inputs") == 30
assert summary.get("production_input_return_packet_blocking_external_inputs") == 1
assert summary.get("production_input_return_packet_blocking_inputs_operator_input_required") == 31
assert summary.get("production_input_return_packet_blocking_inputs_generic_operator_required") == 0
assert summary.get("production_input_return_packet_operator_next_actions_total") == 2
assert summary.get("production_input_return_packet_operator_next_actions_operator_input_required") == 2
assert summary.get("production_input_return_packet_operator_next_actions_generic_blocking") == 0
assert summary.get("production_input_return_packet_raw_files_expected") == 63
assert summary.get("production_input_return_packet_raw_files_missing") == 33
assert summary.get("production_input_return_packet_raw_files_local_observation") == 30
assert summary.get("production_input_return_packet_external_artifacts_operator_required") == 1
assert summary.get("return_acceptance_raw_files_staged") == 0
assert summary.get("return_acceptance_raw_files_local_observation", 0) > 0
assert summary.get("required_evidence_files_ready") == 0
assert summary.get("required_evidence_files_total") == 64
assert summary.get("raw_operator_packet_readiness_decision") == "BLOCKED_ON_OPERATOR_PRODUCTION_EVIDENCE"
assert summary.get("raw_operator_packet_readiness_ready_for_collectors") is False
assert summary.get("raw_operator_packet_readiness_collectors_ready") == 0
assert summary.get("raw_operator_packet_readiness_collectors_blocked") == 9
assert summary.get("raw_operator_packet_readiness_collectors_total") == 9
assert summary.get("raw_operator_packet_readiness_raw_files_ready") == 0
assert summary.get("raw_operator_packet_readiness_raw_files_local_observation") == 63
assert summary.get("raw_operator_packet_readiness_raw_files_total") == 63
assert summary.get("semantic_blocking_items_total", 0) > 0
assert summary.get("semantic_preflight_errors_total", 0) > 0
assert summary.get("external_settlement_handoff_clear") is True
assert summary.get("external_settlement_handoff_decision") == "X0T_EXTERNAL_SETTLEMENT_HANDOFF_BLOCKED_ON_OPERATOR"
assert summary.get("external_settlement_handoff_ready_for_completion_rerun") is False
assert summary.get("external_settlement_capture_preflight_decision") == "CAPTURE_INPUTS_BLOCKED"
assert summary.get("external_settlement_handoff_operator_command_entrypoints_missing") == 0
assert summary.get("external_settlement_handoff_operator_commands_with_shell_redirection_placeholders") == 0
assert summary.get("external_settlement_handoff_operator_command_shell_surface_ready") is True
assert summary.get("x0t_governance_handoff_operator_actions_total") == 5
assert summary.get("x0t_governance_handoff_operator_commands_total") == 5
assert summary.get("x0t_governance_handoff_operator_command_entrypoints_missing") == 0
assert summary.get("x0t_governance_handoff_operator_command_surface_ready") is True
assert summary.get("x0t_governance_handoff_operator_commands_with_shell_redirection_placeholders") == 0
assert summary.get("x0t_governance_handoff_operator_command_shell_surface_ready") is True
assert summary.get("x0t_governance_handoff_operator_sequence_ready") is True
assert summary.get("x0t_contract_handoff_available") is True
assert summary.get("x0t_contract_handoff_decision") == "X0T_CONTRACT_DEPLOYMENT_CONFIG_BLOCKED_ON_OPERATOR"
assert summary.get("x0t_contract_handoff_deployment_ready") is False
assert summary.get("x0t_contract_handoff_approval_value_required") == "apply-bridge-address-base-sepolia"
assert summary.get("x0t_contract_handoff_missing_inputs_total") == 1
assert summary.get("x0t_contract_handoff_operator_actions_total") == 6
assert summary.get("x0t_contract_handoff_operator_approval_required_actions_total") == 1
assert summary.get("x0t_contract_handoff_operator_commands_total") == 5
assert summary.get("x0t_contract_handoff_operator_command_entrypoints_missing") == 0
assert summary.get("x0t_contract_handoff_operator_command_surface_ready") is True
assert summary.get("x0t_contract_handoff_operator_commands_with_shell_redirection_placeholders") == 0
assert summary.get("x0t_contract_handoff_operator_command_shell_surface_ready") is True
assert summary.get("x0t_contract_handoff_operator_sequence_ready") is True
assert summary.get("live_rollout_handoff_available") is True
assert summary.get("live_rollout_handoff_decision") == "LIVE_ROLLOUT_IMAGE_DIGESTS_BLOCKED_ON_OPERATOR"
assert summary.get("live_rollout_handoff_ready_for_completion_rerun") is False
assert summary.get("live_rollout_handoff_can_close_image_digests_blocker") is False
assert summary.get("live_rollout_handoff_missing_inputs_total") == 1
assert summary.get("live_rollout_handoff_operator_actions_total") == 5
assert summary.get("live_rollout_handoff_operator_input_required_actions_total") == 2
assert summary.get("live_rollout_handoff_operator_commands_total") == 4
assert summary.get("live_rollout_handoff_operator_command_entrypoints_missing") == 0
assert summary.get("live_rollout_handoff_operator_command_surface_ready") is True
assert summary.get("live_rollout_handoff_operator_commands_with_shell_redirection_placeholders") == 0
assert summary.get("live_rollout_handoff_operator_command_shell_surface_ready") is True
assert summary.get("live_rollout_handoff_operator_sequence_ready") is True
assert data.get("source_reports")
PY
  then
    pass "integration-spine completion gate runner current shards fail closed"
  else
    fail "integration-spine completion gate runner current shards fail closed"
  fi
  rm -f "${tmp}"
}

run_production_closeout_review_current_smoke_check() {
  local tmp closure_tmp final_tmp code
  tmp="$(mktemp)"
  closure_tmp="$(mktemp)"
  final_tmp="$(mktemp)"
  set +e
  python3 -m src.integration.production_closeout_review \
    --root . \
    --output-json "${tmp}" \
    --output-closure-preflight-json "${closure_tmp}" \
    --output-final-review-json "${final_tmp}" \
    --require-ready >/dev/null 2>&1
  code=$?
  set -e
  if [[ "${code}" -eq 2 ]] && python3 - "${tmp}" "${closure_tmp}" "${final_tmp}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
preflight = json.load(open(sys.argv[2], encoding="utf-8"))
final_review = json.load(open(sys.argv[3], encoding="utf-8"))
summary = data.get("summary", {})
assert data.get("status") == "VERIFIED HERE"
assert data.get("ok") is True
assert data.get("ready") is False
assert data.get("decision") == "CLOSEOUT_REVIEW_BLOCKED_ON_OPERATOR_EVIDENCE"
assert data.get("goal_can_be_marked_complete") is False
assert summary.get("source_errors_total") == 0
assert summary.get("sources_total", 0) > 0
assert summary.get("sources_blocking", 0) > 0
assert summary.get("blocking_inputs_total", 0) > 0
assert summary.get("raw_files_installed") == 0
assert summary.get("raw_files_install_claim_source") == "return_acceptance"
assert summary.get("raw_files_pipeline_reported_installed") == 0
assert summary.get("raw_files_existing_or_retained", 0) > 0
assert summary.get("raw_files_local_observation", 0) > 0
assert summary.get("required_evidence_files_total") == 64
assert summary.get("required_evidence_files_ready", 0) < summary.get("required_evidence_files_total", 0)
assert summary.get("rollup_evidence_files_total") == 64
assert summary.get("rollup_evidence_files_valid") == 0
assert summary.get("rollup_evidence_files_missing") == 1
assert summary.get("rollup_evidence_files_invalid") == 63
assert summary.get("rollup_evidence_files_operator_input_required") == 63
assert summary.get("operator_handoff_source_available") is True
assert summary.get("operator_handoff_source_errors_total") == 0
assert summary.get("top_blockers_total") == 5
assert summary.get("top_blockers_blocking") == 0
assert summary.get("top_blockers_operator_input_required") == 4
assert summary.get("top_blockers_operator_approval_required") == 1
assert summary.get("x0t_contract_surface_clear") is True
assert summary.get("x0t_contract_deployment_ready") is False
assert summary.get("x0t_contract_readiness_decision") == "BLOCKED_ON_DEPLOYMENT_CONFIG"
assert summary.get("x0t_bridge_config_decision") == "X0T_BRIDGE_CONFIG_BLOCKED_ON_OPERATOR"
assert summary.get("external_settlement_handoff_clear") is True
assert summary.get("external_settlement_handoff_decision") == "X0T_EXTERNAL_SETTLEMENT_HANDOFF_BLOCKED_ON_OPERATOR"
assert summary.get("x0t_governance_execute_decision") in {
    "NOT_READY_TIMELOCK_ACTIVE",
    "QUEUED_STATE_AFTER_TIMELOCK_CHECK_REQUIRED",
    "READY_TO_EXECUTE",
    "ALREADY_EXECUTED",
    "VETOED_NOT_EXECUTABLE",
    "NOT_READY_STATE_NOT_EXECUTABLE",
}
assert summary.get("x0t_governance_proposal_executed") is False
assert summary.get("x0t_governance_execute_handoff_decision") in {
    "X0T_GOVERNANCE_EXECUTE_HANDOFF_BLOCKED_ON_READINESS",
    "X0T_GOVERNANCE_EXECUTE_HANDOFF_READY_FOR_OPERATOR_APPROVAL",
    "X0T_GOVERNANCE_EXECUTE_HANDOFF_ALREADY_EXECUTED",
}
assert summary.get("x0t_governance_handoff_available") is True
assert summary.get("x0t_governance_handoff_actionable") is True
assert summary.get("x0t_governance_handoff_approval_value_required") == "execute-proposal-1-base-sepolia"
assert summary.get("x0t_governance_handoff_missing_inputs_total") in {0, 1, 2}
assert summary.get("x0t_governance_handoff_operator_actions_total") == 5
if (
    summary.get("x0t_governance_ready_for_operator_execute") is True
    and summary.get("x0t_governance_proposal_executed") is False
):
    assert summary.get("x0t_governance_handoff_operator_approval_required_actions_total") == 1
assert summary.get("x0t_governance_handoff_operator_commands_total") == 5
assert summary.get("x0t_governance_handoff_operator_command_entrypoints_missing") == 0
assert summary.get("x0t_governance_handoff_operator_command_surface_ready") is True
assert summary.get("x0t_governance_handoff_operator_commands_with_shell_redirection_placeholders") == 0
assert summary.get("x0t_governance_handoff_operator_command_shell_surface_ready") is True
assert summary.get("x0t_governance_handoff_operator_sequence_ready") is True
assert summary.get("external_settlement_handoff_available") is True
assert summary.get("external_settlement_handoff_ready_for_completion_rerun") is False
assert summary.get("external_settlement_capture_preflight_decision") == "CAPTURE_INPUTS_BLOCKED"
assert summary.get("external_settlement_capture_inputs_ready") is False
assert summary.get("external_settlement_handoff_missing_inputs_total") == 5
assert summary.get("external_settlement_handoff_operator_actions_total") == 6
assert summary.get("external_settlement_handoff_operator_input_required_actions_total") == 6
assert summary.get("external_settlement_handoff_operator_commands_total") == 5
assert summary.get("external_settlement_handoff_operator_command_entrypoints_missing") == 0
assert summary.get("external_settlement_handoff_operator_command_surface_ready") is True
assert summary.get("external_settlement_handoff_operator_commands_with_shell_redirection_placeholders") == 0
assert summary.get("external_settlement_handoff_operator_command_shell_surface_ready") is True
assert summary.get("external_settlement_handoff_operator_sequence_ready") is True
assert summary.get("x0t_contract_handoff_available") is True
assert summary.get("x0t_contract_handoff_decision") == "X0T_CONTRACT_DEPLOYMENT_CONFIG_BLOCKED_ON_OPERATOR"
assert summary.get("x0t_contract_handoff_deployment_ready") is False
assert summary.get("x0t_contract_handoff_approval_value_required") == "apply-bridge-address-base-sepolia"
assert summary.get("x0t_contract_handoff_missing_inputs_total") == 1
assert summary.get("x0t_contract_handoff_operator_actions_total") == 6
assert summary.get("x0t_contract_handoff_operator_approval_required_actions_total") == 1
assert summary.get("x0t_contract_handoff_operator_commands_total") == 5
assert summary.get("x0t_contract_handoff_operator_command_entrypoints_missing") == 0
assert summary.get("x0t_contract_handoff_operator_command_surface_ready") is True
assert summary.get("x0t_contract_handoff_operator_commands_with_shell_redirection_placeholders") == 0
assert summary.get("x0t_contract_handoff_operator_command_shell_surface_ready") is True
assert summary.get("x0t_contract_handoff_operator_sequence_ready") is True
assert summary.get("live_rollout_handoff_available") is True
assert summary.get("live_rollout_handoff_decision") == "LIVE_ROLLOUT_IMAGE_DIGESTS_BLOCKED_ON_OPERATOR"
assert summary.get("live_rollout_handoff_ready_for_completion_rerun") is False
assert summary.get("live_rollout_handoff_can_close_image_digests_blocker") is False
assert summary.get("live_rollout_handoff_missing_inputs_total") == 1
assert summary.get("live_rollout_handoff_operator_actions_total") == 5
assert summary.get("live_rollout_handoff_operator_input_required_actions_total") == 2
assert summary.get("live_rollout_handoff_operator_commands_total") == 4
assert summary.get("live_rollout_handoff_operator_command_entrypoints_missing") == 0
assert summary.get("live_rollout_handoff_operator_command_surface_ready") is True
assert summary.get("live_rollout_handoff_operator_commands_with_shell_redirection_placeholders") == 0
assert summary.get("live_rollout_handoff_operator_command_shell_surface_ready") is True
assert summary.get("live_rollout_handoff_operator_sequence_ready") is True
for derived in (preflight, final_review):
    derived_summary = derived.get("summary", {})
    assert derived_summary.get("rollup_evidence_files_operator_input_required") == 63
handoffs = data.get("operator_handoffs", {})
assert handoffs.get("source_artifact") == ".tmp/validation-shards/integration-spine-current-evidence-rollup-current.json"
governance = handoffs.get("x0t_governance_execute", {})
assert governance.get("available") is True
assert governance.get("approval_value_required") == "execute-proposal-1-base-sepolia"
governance_action_ids = {
    item.get("id")
    for item in governance.get("operator_next_actions", [])
    if isinstance(item, dict)
}
assert "execute_with_operator_approval" in governance_action_ids
assert "rerun_completion_and_gap" in governance_action_ids
external = handoffs.get("external_settlement", {})
assert external.get("available") is True
assert external.get("missing_inputs")
assert external.get("missing_inputs")[0].get("id") == "capture_input_preflight"
external_action_ids = {
    item.get("id")
    for item in external.get("operator_next_actions", [])
    if isinstance(item, dict)
}
assert "preflight_capture_inputs" in external_action_ids
assert "verify_live_base_rpc" in external_action_ids
external_action_statuses = {
    item.get("id"): item.get("status")
    for item in external.get("operator_next_actions", [])
    if isinstance(item, dict)
}
assert external_action_statuses.get("preflight_capture_inputs") == "OPERATOR_INPUT_REQUIRED"
assert external_action_statuses.get("verify_live_base_rpc") == "OPERATOR_INPUT_REQUIRED"
x0t_contract = handoffs.get("x0t_contract_deployment", {})
assert x0t_contract.get("available") is True
assert x0t_contract.get("source_artifact") == ".tmp/validation-shards/integration-spine-production-gap-index-current.json"
assert x0t_contract.get("approval_value_required") == "apply-bridge-address-base-sepolia"
assert x0t_contract.get("operator_command_checks")
live_rollout = handoffs.get("live_rollout_image_digests", {})
assert live_rollout.get("available") is True
assert live_rollout.get("source_artifact") == ".tmp/validation-shards/integration-spine-current-evidence-rollup-current.json"
assert live_rollout.get("missing_inputs")
assert live_rollout.get("missing_inputs")[0].get("id") == "live_rollout_image_digest_provenance"
assert live_rollout.get("operator_command_checks")
for derived, decision in (
    (preflight, "PREFLIGHT_BLOCKED_ON_OPERATOR_EVIDENCE"),
    (final_review, "FINAL_REVIEW_BLOCKED_ON_OPERATOR_EVIDENCE"),
):
    derived_summary = derived.get("summary", {})
    assert derived.get("status") == "VERIFIED HERE"
    assert derived.get("ok") is True
    assert derived.get("ready") is False
    assert derived.get("decision") == decision
    assert derived.get("goal_can_be_marked_complete") is False
    assert str(derived.get("schema_version", "")).endswith("v4-repo-generated")
    assert derived_summary.get("raw_files_installed") == 0
    assert derived_summary.get("raw_files_install_claim_source") == "return_acceptance"
    assert derived_summary.get("raw_files_pipeline_reported_installed") == 0
    assert derived_summary.get("raw_files_local_observation", 0) > 0
    assert derived_summary.get("external_settlement_handoff_decision") == "X0T_EXTERNAL_SETTLEMENT_HANDOFF_BLOCKED_ON_OPERATOR"
    assert derived_summary.get("x0t_governance_execute_decision") in {
        "NOT_READY_TIMELOCK_ACTIVE",
        "QUEUED_STATE_AFTER_TIMELOCK_CHECK_REQUIRED",
        "READY_TO_EXECUTE",
        "ALREADY_EXECUTED",
        "VETOED_NOT_EXECUTABLE",
        "NOT_READY_STATE_NOT_EXECUTABLE",
    }
    assert derived_summary.get("x0t_governance_proposal_executed") is False
    assert derived_summary.get("operator_handoff_source_available") is True
    assert derived_summary.get("x0t_governance_handoff_operator_sequence_ready") is True
    assert derived_summary.get("external_settlement_handoff_operator_sequence_ready") is True
    assert derived_summary.get("external_settlement_handoff_operator_input_required_actions_total") == 6
    assert derived_summary.get("x0t_contract_handoff_operator_sequence_ready") is True
    assert derived_summary.get("live_rollout_handoff_operator_sequence_ready") is True
    assert derived.get("operator_handoffs", {}).get("external_settlement", {}).get("operator_command_checks")
    assert derived.get("operator_handoffs", {}).get("x0t_contract_deployment", {}).get("operator_command_checks")
    assert derived.get("operator_handoffs", {}).get("live_rollout_image_digests", {}).get("operator_command_checks")
    derived_external = derived.get("operator_handoffs", {}).get("external_settlement", {})
    derived_statuses = {
        item.get("id"): item.get("status")
        for item in derived_external.get("operator_next_actions", [])
        if isinstance(item, dict)
    }
    assert derived_statuses.get("preflight_capture_inputs") == "OPERATOR_INPUT_REQUIRED"
    assert derived_statuses.get("verify_live_base_rpc") == "OPERATOR_INPUT_REQUIRED"
PY
  then
    pass "integration-spine production closeout review current shards fail closed"
  else
    fail "integration-spine production closeout review current shards fail closed"
  fi
  rm -f "${tmp}" "${closure_tmp}" "${final_tmp}"
}

run_completion_audit_current_smoke_check() {
  local tmp code
  tmp="$(mktemp)"
  set +e
  python3 -m src.integration.completion_audit --root . --require-complete >"${tmp}" 2>/dev/null
  code=$?
  set -e
  if [[ "${code}" -eq 2 ]] && python3 - "${tmp}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
summary = data.get("summary", {})
assert data.get("completion_decision") == "NOT_COMPLETE"
assert data.get("goal_can_be_marked_complete") is False
assert summary.get("checklist_total", 0) > 0
assert summary.get("checklist_blocking", 0) > 0
assert summary.get("checklist_generic_blocking") == 0
assert summary.get("blocking_items_generic_blocking") == 0
assert summary.get("checklist_operator_input_required") == 8
assert summary.get("checklist_operator_approval_required") == 1
assert summary.get("checklist_after_blockers") == 1
status_counts = summary.get("checklist_status_counts", {})
assert status_counts.get("BLOCKING", 0) == 0
assert status_counts.get("OPERATOR_INPUT_REQUIRED") == 8
assert status_counts.get("OPERATOR_APPROVAL_REQUIRED") == 1
assert status_counts.get("AFTER_BLOCKERS") == 1
assert summary.get("production_readiness_passed") is False
assert summary.get("raw_operator_packet_readiness_decision") == "BLOCKED_ON_OPERATOR_PRODUCTION_EVIDENCE"
assert summary.get("raw_operator_packet_readiness_ready_for_collectors") is False
assert summary.get("raw_operator_packet_readiness_collectors_ready") == 0
assert summary.get("raw_operator_packet_readiness_collectors_blocked") == 9
assert summary.get("raw_operator_packet_readiness_collectors_total") == 9
assert summary.get("raw_operator_packet_readiness_raw_files_ready") == 0
assert summary.get("raw_operator_packet_readiness_raw_files_local_observation") == 63
assert summary.get("raw_operator_packet_readiness_raw_files_total") == 63
assert summary.get("x0t_governance_execute_decision") in {
    "NOT_READY_TIMELOCK_ACTIVE",
    "QUEUED_STATE_AFTER_TIMELOCK_CHECK_REQUIRED",
    "READY_TO_EXECUTE",
    "ALREADY_EXECUTED",
}
assert summary.get("x0t_governance_execute_handoff_actionable") is True
assert summary.get("x0t_governance_handoff_operator_actions_total") == 5
assert summary.get("x0t_governance_handoff_operator_commands_total") == 5
assert summary.get("x0t_governance_handoff_operator_command_entrypoints_missing") == 0
assert summary.get("x0t_governance_handoff_operator_command_surface_ready") is True
assert summary.get("x0t_governance_handoff_operator_commands_with_shell_redirection_placeholders") == 0
assert summary.get("x0t_governance_handoff_operator_command_shell_surface_ready") is True
assert summary.get("x0t_governance_handoff_operator_sequence_ready") is True
assert summary.get("x0t_governance_execute_handoff_decision") in {
    "X0T_GOVERNANCE_EXECUTE_HANDOFF_BLOCKED_ON_READINESS",
    "X0T_GOVERNANCE_EXECUTE_HANDOFF_READY_FOR_OPERATOR_APPROVAL",
    "X0T_GOVERNANCE_EXECUTE_HANDOFF_ALREADY_EXECUTED",
}
assert summary.get("x0t_contract_handoff_available") is True
assert summary.get("x0t_contract_handoff_decision") == "X0T_CONTRACT_DEPLOYMENT_CONFIG_BLOCKED_ON_OPERATOR"
assert summary.get("x0t_contract_handoff_deployment_ready") is False
assert summary.get("x0t_contract_handoff_approval_value_required") == "apply-bridge-address-base-sepolia"
assert summary.get("x0t_contract_handoff_missing_inputs_total") == 1
assert summary.get("x0t_contract_handoff_operator_actions_total") == 6
assert summary.get("x0t_contract_handoff_operator_approval_required_actions_total") == 1
assert summary.get("x0t_contract_handoff_operator_commands_total") == 5
assert summary.get("x0t_contract_handoff_operator_command_entrypoints_missing") == 0
assert summary.get("x0t_contract_handoff_operator_command_surface_ready") is True
assert summary.get("x0t_contract_handoff_operator_commands_with_shell_redirection_placeholders") == 0
assert summary.get("x0t_contract_handoff_operator_command_shell_surface_ready") is True
assert summary.get("x0t_contract_handoff_operator_sequence_ready") is True
assert summary.get("live_rollout_handoff_available") is True
assert summary.get("live_rollout_handoff_decision") == "LIVE_ROLLOUT_IMAGE_DIGESTS_BLOCKED_ON_OPERATOR"
assert summary.get("live_rollout_handoff_ready_for_completion_rerun") is False
assert summary.get("live_rollout_handoff_can_close_image_digests_blocker") is False
assert summary.get("live_rollout_handoff_missing_inputs_total") == 1
assert summary.get("live_rollout_handoff_operator_actions_total") == 5
assert summary.get("live_rollout_handoff_operator_input_required_actions_total") == 2
assert summary.get("live_rollout_handoff_operator_commands_total") == 4
assert summary.get("live_rollout_handoff_operator_command_entrypoints_missing") == 0
assert summary.get("live_rollout_handoff_operator_command_surface_ready") is True
assert summary.get("live_rollout_handoff_operator_commands_with_shell_redirection_placeholders") == 0
assert summary.get("live_rollout_handoff_operator_command_shell_surface_ready") is True
assert summary.get("live_rollout_handoff_operator_sequence_ready") is True
assert summary.get("external_settlement_handoff_clear") is True
assert summary.get("external_settlement_handoff_decision") == "X0T_EXTERNAL_SETTLEMENT_HANDOFF_BLOCKED_ON_OPERATOR"
assert summary.get("external_settlement_handoff_ready_for_completion_rerun") is False
assert summary.get("external_settlement_capture_preflight_decision") == "CAPTURE_INPUTS_BLOCKED"
assert summary.get("external_settlement_handoff_operator_command_entrypoints_missing") == 0
assert summary.get("external_settlement_handoff_operator_commands_with_shell_redirection_placeholders") == 0
assert summary.get("external_settlement_handoff_operator_command_shell_surface_ready") is True
assert isinstance(summary.get("x0t_governance_proposal_executed"), bool)
PY
  then
    pass "integration-spine completion audit current shards fail closed"
  else
    fail "integration-spine completion audit current shards fail closed"
  fi
  rm -f "${tmp}"
}

run_code_wiring_current_smoke_check() {
  local tmp code
  tmp="$(mktemp)"
  set +e
  python3 -m src.integration.code_wiring \
    --root . \
    --output-json "${tmp}" \
    --require-verified >/dev/null 2>&1
  code=$?
  set -e
  if [[ "${code}" -eq 0 ]] && python3 - "${tmp}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
summary = data.get("summary", {})
assert data.get("status") == "VERIFIED HERE"
assert data.get("ok") is True
assert data.get("decision") == "LOCAL_CODE_WIRING_VERIFIED"
assert data.get("goal_can_be_marked_complete") is False
assert data.get("mutates_runtime") is False
assert data.get("contacts_live_systems") is False
assert data.get("submits_transaction") is False
assert summary.get("required_wiring_keys_total") == 5
assert summary.get("wiring_keys_covered") == 5
assert summary.get("trace_cases_failed") == 0
assert summary.get("canonical_identity_consistent") is True
assert summary.get("policy_before_actuator_verified") is True
assert summary.get("simulated_actuator_blocks_settlement") is True
assert summary.get("settlement_failure_fails_closed") is True
PY
  then
    pass "integration-spine code wiring evidence is executable and fail-closed"
  else
    fail "integration-spine code wiring evidence is executable and fail-closed"
  fi
  rm -f "${tmp}"
}

run_production_gap_index_current_smoke_check() {
  local tmp md_tmp code
  tmp="$(mktemp)"
  md_tmp="$(mktemp)"
  set +e
  python3 -m src.integration.production_gap_index \
    --root . \
    --output-json "${tmp}" \
    --output-md "${md_tmp}" \
    --require-clear >/dev/null 2>&1
  code=$?
  set -e
  if [[ "${code}" -eq 2 ]] && python3 - "${tmp}" "${md_tmp}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
markdown = open(sys.argv[2], encoding="utf-8").read()
summary = data.get("summary", {})
assert data.get("status") == "VERIFIED HERE"
assert data.get("ok") is True
assert data.get("decision") == "BLOCKED_ON_OPERATOR_EVIDENCE"
assert data.get("goal_can_be_marked_complete") is False
assert summary.get("pending_evidence_keys", 0) > 0
assert summary.get("source_artifacts_clear") is False
assert summary.get("completion_audit_clear") is False
assert summary.get("required_evidence_keys_total") == 10
assert summary.get("route_missing") == 0
assert summary.get("import_mismatches") == 0
completion_total = summary.get("completion_checklist_total")
completion_passed = summary.get("completion_checklist_passed")
completion_blocking = summary.get("completion_checklist_blocking")
completion_remaining = summary.get("completion_checklist_remaining")
assert isinstance(completion_total, int) and completion_total > 0
assert isinstance(completion_passed, int) and completion_passed > 0
assert isinstance(completion_blocking, int) and completion_blocking > 0
assert completion_remaining == max(completion_total - completion_passed, 0)
assert completion_blocking == completion_remaining
assert summary.get("completion_local_wiring_passed") is True
assert summary.get("completion_production_readiness_passed") is False
assert summary.get("raw_install_claim_source") == "return_acceptance"
assert summary.get("current_raw_files_installed") == 0
assert summary.get("coverage_raw_files_reported_installed") == 0
assert summary.get("return_acceptance_raw_files_staged") == 0
assert summary.get("return_acceptance_raw_files_local_observation", 0) > 0
assert summary.get("raw_operator_packet_readiness_decision") == "BLOCKED_ON_OPERATOR_PRODUCTION_EVIDENCE"
assert summary.get("raw_operator_packet_readiness_ready_for_collectors") is False
assert summary.get("raw_operator_packet_readiness_collectors_ready") == 0
assert summary.get("raw_operator_packet_readiness_collectors_blocked") == 9
assert summary.get("raw_operator_packet_readiness_collectors_total") == 9
assert summary.get("raw_operator_packet_readiness_raw_files_ready") == 0
assert summary.get("raw_operator_packet_readiness_raw_files_local_observation") == 63
assert summary.get("raw_operator_packet_readiness_raw_files_total") == 63
assert summary.get("x0t_contract_operator_handoff_available") is True
assert summary.get("x0t_contract_operator_handoff_decision") == "X0T_CONTRACT_DEPLOYMENT_CONFIG_BLOCKED_ON_OPERATOR"
assert summary.get("x0t_contract_operator_actions_total") == 6
assert summary.get("x0t_contract_operator_command_entrypoints_missing") == 0
assert summary.get("x0t_contract_operator_command_surface_ready") is True
assert summary.get("x0t_contract_approval_value_required") == "apply-bridge-address-base-sepolia"
x0t_contract_handoff = data.get("x0t_contract_operator_handoff", {})
assert x0t_contract_handoff.get("available") is True
assert x0t_contract_handoff.get("decision") == "X0T_CONTRACT_DEPLOYMENT_CONFIG_BLOCKED_ON_OPERATOR"
assert x0t_contract_handoff.get("deployment_ready") is False
assert x0t_contract_handoff.get("approval_env") == "X0T_APPLY_BRIDGE_ADDRESS_APPROVAL"
assert x0t_contract_handoff.get("approval_value_required") == "apply-bridge-address-base-sepolia"
assert x0t_contract_handoff.get("missing_inputs")
assert x0t_contract_handoff.get("missing_inputs")[0].get("id") == "operator_contract_addresses"
x0t_contract_action_ids = {
    item.get("id")
    for item in x0t_contract_handoff.get("operator_next_actions", [])
    if isinstance(item, dict)
}
assert "provide_bridge_address" in x0t_contract_action_ids
assert "validate_bridge_address" in x0t_contract_action_ids
assert "apply_bridge_address_with_operator_approval" in x0t_contract_action_ids
assert "rerun_contract_readiness" in x0t_contract_action_ids
x0t_contract_command_ids = {
    item.get("action_id")
    for item in x0t_contract_handoff.get("operator_command_checks", [])
    if isinstance(item, dict)
}
assert "validate_bridge_address" in x0t_contract_command_ids
assert "apply_bridge_address_with_operator_approval" in x0t_contract_command_ids
assert "rerun_contract_readiness" in x0t_contract_command_ids
assert summary.get("x0t_governance_execute_readiness_available") is True
assert summary.get("x0t_governance_execute_decision") in {
    "NOT_READY_TIMELOCK_ACTIVE",
    "QUEUED_STATE_AFTER_TIMELOCK_CHECK_REQUIRED",
    "READY_TO_EXECUTE",
    "ALREADY_EXECUTED",
}
assert isinstance(summary.get("x0t_governance_proposal_executed"), bool)
assert summary.get("x0t_governance_execute_handoff_available") is True
assert summary.get("x0t_governance_execute_handoff_clear") is True
assert summary.get("x0t_governance_execute_handoff_missing_inputs_total") in {0, 1, 2}
assert summary.get("x0t_governance_execute_handoff_operator_actions_total") == 5
assert summary.get("x0t_governance_execute_handoff_operator_commands_total") == 5
assert summary.get("x0t_governance_execute_handoff_operator_command_entrypoints_missing") == 0
assert summary.get("x0t_governance_execute_handoff_operator_command_surface_ready") is True
assert summary.get("x0t_governance_execute_handoff_operator_commands_with_shell_redirection_placeholders") == 0
assert summary.get("x0t_governance_execute_handoff_operator_command_shell_surface_ready") is True
assert summary.get("x0t_governance_execute_handoff_operator_sequence_ready") is True
governance_handoff = data.get("x0t_governance_operator_handoff", {})
assert governance_handoff.get("available") is True
assert governance_handoff.get("decision") in {
    "X0T_GOVERNANCE_EXECUTE_HANDOFF_BLOCKED_ON_READINESS",
    "X0T_GOVERNANCE_EXECUTE_HANDOFF_READY_FOR_OPERATOR_APPROVAL",
    "X0T_GOVERNANCE_EXECUTE_HANDOFF_ALREADY_EXECUTED",
}
assert governance_handoff.get("actionable") is True
assert isinstance(governance_handoff.get("ready_for_operator_execute"), bool)
assert governance_handoff.get("approval_value_required") == "execute-proposal-1-base-sepolia"
assert governance_handoff.get("operator_next_actions")
governance_action_ids = {
    item.get("id")
    for item in governance_handoff.get("operator_next_actions", [])
    if isinstance(item, dict)
}
assert "refresh_readiness" in governance_action_ids
assert "execute_with_operator_approval" in governance_action_ids
assert "rerun_completion_and_gap" in governance_action_ids
assert governance_handoff.get("operator_command_checks")
governance_command_action_ids = {
    item.get("action_id")
    for item in governance_handoff.get("operator_command_checks", [])
    if isinstance(item, dict)
}
assert "refresh_readiness" in governance_command_action_ids
assert "execute_with_operator_approval" in governance_command_action_ids
assert "rerun_completion_and_gap" in governance_command_action_ids
assert summary.get("external_settlement_handoff_available") is True
assert summary.get("external_settlement_handoff_clear") is True
assert summary.get("external_settlement_handoff_decision") == "X0T_EXTERNAL_SETTLEMENT_HANDOFF_BLOCKED_ON_OPERATOR"
assert summary.get("external_settlement_handoff_ready_for_completion_rerun") is False
assert summary.get("external_settlement_capture_preflight_decision") == "CAPTURE_INPUTS_BLOCKED"
assert summary.get("external_settlement_capture_inputs_ready") is False
assert summary.get("external_settlement_handoff_missing_inputs_total") == 5
assert summary.get("external_settlement_handoff_operator_actions_total") == 6
assert summary.get("external_settlement_handoff_operator_commands_total") == 5
assert summary.get("external_settlement_handoff_operator_command_entrypoints_missing") == 0
assert summary.get("external_settlement_handoff_operator_command_surface_ready") is True
assert summary.get("external_settlement_handoff_operator_commands_with_shell_redirection_placeholders") == 0
assert summary.get("external_settlement_handoff_operator_command_shell_surface_ready") is True
assert summary.get("live_rollout_handoff_available") is True
assert summary.get("live_rollout_handoff_clear") is True
assert summary.get("live_rollout_handoff_decision") == "LIVE_ROLLOUT_IMAGE_DIGESTS_BLOCKED_ON_OPERATOR"
assert summary.get("live_rollout_ready_for_completion_rerun") is False
assert summary.get("live_rollout_can_close_image_digests_blocker") is False
assert summary.get("live_rollout_handoff_missing_inputs_total") == 1
assert summary.get("live_rollout_handoff_operator_actions_total") == 5
assert summary.get("live_rollout_handoff_operator_commands_total") == 4
assert summary.get("live_rollout_handoff_operator_command_entrypoints_missing") == 0
assert summary.get("live_rollout_handoff_operator_command_surface_ready") is True
assert summary.get("live_rollout_handoff_operator_commands_with_shell_redirection_placeholders") == 0
assert summary.get("live_rollout_handoff_operator_command_shell_surface_ready") is True
handoff = data.get("external_settlement_operator_handoff", {})
assert handoff.get("available") is True
assert handoff.get("decision") == "X0T_EXTERNAL_SETTLEMENT_HANDOFF_BLOCKED_ON_OPERATOR"
assert handoff.get("ready_for_completion_rerun") is False
assert handoff.get("capture_preflight_decision") == "CAPTURE_INPUTS_BLOCKED"
assert handoff.get("capture_inputs_ready") is False
assert handoff.get("missing_inputs")
assert handoff.get("missing_inputs")[0].get("id") == "capture_input_preflight"
assert handoff.get("operator_next_actions")
action_ids = {item.get("id") for item in handoff.get("operator_next_actions", []) if isinstance(item, dict)}
assert "preflight_capture_inputs" in action_ids
assert "verify_live_base_rpc" in action_ids
action_statuses = {
    item.get("id"): item.get("status")
    for item in handoff.get("operator_next_actions", [])
    if isinstance(item, dict)
}
assert action_statuses.get("preflight_capture_inputs") == "OPERATOR_INPUT_REQUIRED"
assert action_statuses.get("verify_live_base_rpc") == "OPERATOR_INPUT_REQUIRED"
assert handoff.get("operator_command_checks")
command_action_ids = {item.get("action_id") for item in handoff.get("operator_command_checks", []) if isinstance(item, dict)}
assert "preflight_capture_inputs" in command_action_ids
assert "verify_live_base_rpc" in command_action_ids
live_rollout_handoff = data.get("live_rollout_operator_handoff", {})
assert live_rollout_handoff.get("available") is True
assert live_rollout_handoff.get("decision") == "LIVE_ROLLOUT_IMAGE_DIGESTS_BLOCKED_ON_OPERATOR"
assert live_rollout_handoff.get("rollout_decision") == "CANNOT_CLOSE_WITH_CURRENT_RETAINED_ARTIFACTS"
assert live_rollout_handoff.get("ready_for_completion_rerun") is False
assert live_rollout_handoff.get("missing_inputs")
assert live_rollout_handoff.get("missing_inputs")[0].get("id") == "live_rollout_image_digest_provenance"
assert live_rollout_handoff.get("operator_next_actions")
live_rollout_action_ids = {
    item.get("id")
    for item in live_rollout_handoff.get("operator_next_actions", [])
    if isinstance(item, dict)
}
assert "render_template_pack" in live_rollout_action_ids
assert "return_digest_pinned_evidence" in live_rollout_action_ids
assert "verify_live_rollout_evidence_gate" in live_rollout_action_ids
assert "rerun_rollout_provenance" in live_rollout_action_ids
assert "rerun_current_evidence_rollup" in live_rollout_action_ids
live_rollout_command_action_ids = {
    item.get("action_id")
    for item in live_rollout_handoff.get("operator_command_checks", [])
    if isinstance(item, dict)
}
assert "render_template_pack" in live_rollout_command_action_ids
assert "verify_live_rollout_evidence_gate" in live_rollout_command_action_ids
assert "rerun_rollout_provenance" in live_rollout_command_action_ids
assert "rerun_current_evidence_rollup" in live_rollout_command_action_ids
assert data.get("operator_priority_order")
assert "Integration Spine Production Gap Index" in markdown
assert "pending evidence keys" in markdown
assert "X0T Contract Deployment Operator Handoff" in markdown
assert "operator_contract_addresses" in markdown
assert "apply_x0t_bridge_contract_address.py --bridge-address" in markdown
assert "apply_bridge_address_with_operator_approval" in markdown
assert "X0T_APPLY_BRIDGE_ADDRESS_APPROVAL" in markdown
assert "X0T Governance Execute Operator Handoff" in markdown
assert "execute_with_operator_approval" in markdown
assert "requires operator approval" in markdown
assert "rerun_completion_and_gap" in markdown
assert "external settlement handoff" in markdown
assert "External Settlement Operator Handoff" in markdown
assert "capture_input_preflight" in markdown
assert "preflight_capture_inputs" in markdown
assert "verify_live_base_rpc" in markdown
assert "OPERATOR_INPUT_REQUIRED" in markdown
assert "Live Rollout Image Digest Operator Handoff" in markdown
assert "live_rollout_image_digest_provenance" in markdown
assert "scaffold_live_rollout_image_provenance_evidence.py --write-template-files --force" in markdown
assert "verify_live_rollout_evidence_gate" in markdown
assert "rerun_rollout_provenance" in markdown
assert "Command Surface" in markdown
assert "Operator Priority Order" in markdown
assert "collector:" in markdown
assert "verify:" in markdown
assert "raw files to replace:" in markdown
PY
  then
    pass "integration-spine production gap index current shards fail closed"
  else
    fail "integration-spine production gap index current shards fail closed"
  fi
  rm -f "${tmp}" "${md_tmp}"
}

run_x0t_contract_readiness_current_smoke_check() {
  local output code
  output=".tmp/validation-shards/x0t-contract-readiness-current.json"
  set +e
  python3 -m src.integration.x0t_contract_readiness \
    --root . \
    --write-json \
    --output-json "${output}" \
    --require-ready >/dev/null 2>&1
  code=$?
  set -e
  if [[ "${code}" -eq 2 ]] && python3 - "${output}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
summary = data.get("summary", {})
deployment = data.get("deployment_manifest", {})
operator_configs = data.get("operator_configs", {})
missing = data.get("missing_inputs", [])
missing_ids = {item.get("id") for item in missing if isinstance(item, dict)}
not_verified = data.get("not_verified_yet", [])
manifest_addresses = {
    item.get("field"): item
    for item in deployment.get("address_checks", [])
    if isinstance(item, dict)
}
operator_address_checks = [
    address
    for check in operator_configs.get("checks", [])
    for address in check.get("addresses", [])
    if isinstance(address, dict)
]

assert data.get("status") == "VERIFIED HERE"
assert data.get("ok") is True
assert data.get("schema_version") == "x0tta6bl4-x0t-contract-readiness-v1"
assert data.get("contract_readiness_clear") is False
assert data.get("goal_can_be_marked_complete") is False
assert data.get("mutates_chain") is False
assert data.get("runs_live_rpc") is False
assert data.get("submits_transaction") is False
assert data.get("decision") == "BLOCKED_ON_DEPLOYMENT_CONFIG"
assert summary.get("build_env_ready") is True
assert summary.get("effective_node_runtime_ready") is True
assert summary.get("node_runtime_ready_source") == "contract_build_verification"
assert summary.get("base_sepolia_manifest_ready") is True
assert summary.get("operator_configs_ready") is False
assert summary.get("contract_dependencies_ready") is True
assert summary.get("contract_build_verification_ready") is True
assert summary.get("legacy_contract_surface_ready") is True
assert summary.get("bridge_contract_source_ready") is True
assert "operator_contract_addresses" in missing_ids
assert "x0t_bridge_contract_source_surface" not in missing_ids
assert "node_runtime" not in missing_ids
assert "contract_build_verification" not in missing_ids
assert "base_sepolia_deployment_manifest" not in missing_ids
assert manifest_addresses.get("MeshGovernance", {}).get("value") == "0xf1B0086962e41710968D81F099c8ced23b97D2d2"
assert manifest_addresses.get("MeshGovernance", {}).get("ready") is True
assert manifest_addresses.get("X0TToken", {}).get("value") == "0x91818F5A6D7ace609D3890Bd1f538c1414Fd87A1"
assert manifest_addresses.get("X0TToken", {}).get("ready") is True
assert any(
    item.get("address_kind") == "governance_contract"
    and item.get("value") == "0xf1B0086962e41710968D81F099c8ced23b97D2d2"
    and item.get("ready") is True
    for item in operator_address_checks
)
assert any(
    item.get("address_kind") == "bridge_contract"
    and item.get("status") == "MISSING_BRIDGE_CONTRACT_ADDRESS"
    and item.get("ready") is False
    for item in operator_address_checks
)
assert "deployed bridge contract address for operator bridge config" in not_verified
assert "successful Hardhat compile/test under the required Node runtime" not in not_verified
assert "authoritative Base Sepolia deployment manifest with non-placeholder addresses" not in not_verified
PY
  then
    pass "X0T contract/deployment readiness current shard is verified and fail-closed"
  else
    fail "X0T contract/deployment readiness current shard is verified and fail-closed"
  fi
}

run_x0t_bridge_config_current_smoke_check() {
  local output reject_tmp code reject_code
  output=".tmp/validation-shards/x0t-bridge-config-current.json"
  reject_tmp="$(mktemp)"
  set +e
  python3 scripts/ops/apply_x0t_bridge_contract_address.py \
    --root . \
    --write-json \
    --output-json "${output}" >/dev/null 2>&1
  code=$?
  python3 scripts/ops/apply_x0t_bridge_contract_address.py \
    --root . \
    --bridge-address "0xf1B0086962e41710968D81F099c8ced23b97D2d2" \
    --write-json \
    --output-json "${reject_tmp}" \
    --require-input-ready >/dev/null 2>&1
  reject_code=$?
  set -e
  if [[ "${code}" -eq 0 ]] && [[ "${reject_code}" -eq 2 ]] && python3 - "${output}" "${reject_tmp}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
reject = json.load(open(sys.argv[2], encoding="utf-8"))
summary = data.get("summary", {})
missing = data.get("missing_inputs", [])
deployment = data.get("deployment_addresses", {})
write = data.get("write", {})
config = data.get("config", {})

assert data.get("status") == "VERIFIED HERE"
assert data.get("ok") is True
assert data.get("schema_version") == "x0tta6bl4-x0t-bridge-config-v1"
assert data.get("decision") == "X0T_BRIDGE_CONFIG_BLOCKED_ON_OPERATOR"
assert data.get("bridge_config_ready") is False
assert data.get("goal_can_be_marked_complete") is False
assert data.get("mutates_chain") is False
assert data.get("runs_live_rpc") is False
assert data.get("submits_transaction") is False
assert data.get("mutates_config") is False
assert summary.get("bridge_address_input_ready") is False
assert summary.get("configured_bridge_ready") is False
assert summary.get("write_performed") is False
assert summary.get("missing_inputs_total") == 1
assert summary.get("missing_inputs_operator_input_required") == 1
assert summary.get("missing_inputs_generic_operator_required") == 0
assert missing and missing[0].get("id") == "bridge_contract_address"
assert missing[0].get("status") == "OPERATOR_INPUT_REQUIRED"
assert missing[0].get("environment") == "X0T_BRIDGE_CONTRACT_ADDRESS"
assert "must not be zero or placeholder" in missing[0].get("reason", "")
assert config.get("configured_bridge_address") == "0x0000000000000000000000000000000000000000"
assert deployment.get("MeshGovernance") == "0xf1B0086962e41710968D81F099c8ced23b97D2d2"
assert deployment.get("X0TToken") == "0x91818F5A6D7ace609D3890Bd1f538c1414Fd87A1"
assert write.get("approval_env") == "X0T_APPLY_BRIDGE_ADDRESS_APPROVAL"
assert write.get("approval_value_required") == "apply-bridge-address-base-sepolia"

assert reject.get("decision") == "X0T_BRIDGE_CONFIG_BLOCKED_ON_OPERATOR"
assert reject.get("summary", {}).get("bridge_address_input_ready") is False
assert any(
    "must not equal MeshGovernance" in error
    for error in reject.get("input", {}).get("errors", [])
)
assert reject.get("mutates_chain") is False
assert reject.get("submits_transaction") is False
PY
  then
    pass "X0T bridge config current shard is actionable and fail-closed"
  else
    fail "X0T bridge config current shard is actionable and fail-closed"
  fi
  rm -f "${reject_tmp}"
}

run_x0t_contract_build_verification_artifact_smoke_check() {
  local output code
  output=".tmp/validation-shards/x0t-contract-build-verification-current.json"
  set +e
  python3 scripts/ops/verify_x0t_contract_build.py \
    --root . \
    --output-json "${output}" \
    --write-json \
    --timeout 600 \
    --require-verified >/dev/null 2>&1
  code=$?
  set -e
  if [[ "${code}" -eq 0 ]] && python3 - "${output}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
summary = data.get("summary", {})
commands = {
    item.get("name"): item
    for item in data.get("commands", [])
    if isinstance(item, dict)
}
assert data.get("status") == "VERIFIED HERE"
assert data.get("ok") is True
assert data.get("schema_version") == "x0tta6bl4-x0t-contract-build-verification-v1"
assert data.get("decision") == "X0T_CONTRACT_BUILD_VERIFIED"
assert data.get("contract_build_verified") is True
assert data.get("goal_can_be_marked_complete") is False
assert data.get("mutates_chain") is False
assert data.get("runs_live_rpc") is False
assert data.get("submits_transaction") is False
assert data.get("mutates_local_build_artifacts") is True
assert summary.get("required_node_package") == "node@22.10.0"
assert summary.get("required_node_runtime_ready") is True
assert summary.get("hardhat_compile_ready") is True
assert summary.get("hardhat_test_ready") is True
assert summary.get("commands_total") == 3
assert summary.get("commands_failed") == 0
assert commands.get("node_version", {}).get("stdout_tail", "").strip().startswith("v22.10.")
assert commands.get("hardhat_compile", {}).get("ok") is True
assert commands.get("hardhat_test", {}).get("ok") is True
PY
  then
    pass "X0T contract build verification artifact proves Node 22 Hardhat compile/test"
  else
    fail "X0T contract build verification artifact proves Node 22 Hardhat compile/test"
  fi
}

run_x0t_governance_execute_readiness_artifact_smoke_check() {
  local tmp code
  tmp="$(mktemp)"
  set +e
  python3 scripts/ops/check_x0t_governance_execute_readiness.py \
    --validate-json .tmp/validation-shards/x0t-governance-execute-proposal-1-readiness-current.json \
    --output-validation-json "${tmp}" \
    --require-valid >/dev/null 2>&1
  code=$?
  set -e
  if [[ "${code}" -eq 0 ]] && python3 - "${tmp}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
summary = data.get("summary", {})
assert data.get("status") == "VERIFIED HERE"
assert data.get("ok") is True
assert data.get("decision") == "VALID_EXECUTE_READINESS_ARTIFACT"
assert data.get("goal_can_be_marked_complete") is False
assert data.get("runs_live_rpc") is False
assert data.get("mutates_chain") is False
assert data.get("submits_transaction") is False
assert summary.get("errors_total") == 0
assert summary.get("source_decision") in {
    "NOT_READY_TIMELOCK_ACTIVE",
    "QUEUED_STATE_AFTER_TIMELOCK_CHECK_REQUIRED",
    "READY_TO_EXECUTE",
    "ALREADY_EXECUTED",
    "VETOED_NOT_EXECUTABLE",
    "NOT_READY_STATE_NOT_EXECUTABLE",
}
PY
  then
    pass "X0T governance execute-readiness artifact is read-only and internally consistent"
  else
    fail "X0T governance execute-readiness artifact is read-only and internally consistent"
  fi
  rm -f "${tmp}"
}

run_x0t_governance_execute_handoff_smoke_check() {
  local tmp code
  tmp="$(mktemp)"
  set +e
  python3 scripts/ops/run_x0t_governance_execute_handoff.py \
    --output-json "${tmp}" \
    --require-actionable >/dev/null 2>&1
  code=$?
  set -e
  if [[ "${code}" -eq 0 ]] && python3 - "${tmp}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
summary = data.get("summary", {})
approval = data.get("approval_boundary", {})
assert data.get("status") == "VERIFIED HERE"
assert data.get("ok") is True
assert str(data.get("schema_version", "")).endswith("v2-repo-generated")
assert data.get("handoff_actionable") is True
assert data.get("goal_can_be_marked_complete") is False
assert data.get("mutates_chain") is False
assert data.get("runs_live_rpc") is False
assert data.get("submits_transaction") is False
assert approval.get("approval_env") == "X0T_EXECUTE_PROPOSAL_APPROVAL"
assert approval.get("expected_value") == "execute-proposal-1-base-sepolia"
assert approval.get("can_submit_without_operator_approval") is False
assert summary.get("readiness_decision") in {
    "NOT_READY_TIMELOCK_ACTIVE",
    "QUEUED_STATE_AFTER_TIMELOCK_CHECK_REQUIRED",
    "READY_TO_EXECUTE",
    "ALREADY_EXECUTED",
    "VETOED_NOT_EXECUTABLE",
    "NOT_READY_STATE_NOT_EXECUTABLE",
}
assert summary.get("operator_actions_total") == 5
assert summary.get("operator_commands_total") == 5
assert summary.get("operator_command_entrypoints_missing") == 0
assert summary.get("operator_command_surface_ready") is True
assert summary.get("operator_commands_with_shell_redirection_placeholders") == 0
assert summary.get("operator_command_shell_surface_ready") is True
assert summary.get("operator_sequence_ready") is True
assert summary.get("missing_inputs_generic_operator_required") == 0
if summary.get("readiness_decision") == "READY_TO_EXECUTE":
    assert summary.get("missing_inputs_operator_approval_required") == 1
    assert summary.get("missing_inputs_operator_input_required") == 1
    statuses = {
        item.get("id"): item.get("status")
        for item in data.get("missing_inputs", [])
        if isinstance(item, dict)
    }
    assert statuses.get("explicit_operator_approval") == "OPERATOR_APPROVAL_REQUIRED"
    assert statuses.get("operator_private_key") == "OPERATOR_INPUT_REQUIRED"
assert data.get("operator_command_checks")
assert all(item.get("entrypoint_exists") is True for item in data.get("operator_command_checks", []))
assert all(item.get("shell_redirection_placeholder_detected") is False for item in data.get("operator_command_checks", []))
commands = [item.get("command", "") for item in data.get("operator_next_actions", [])]
assert any('PRIVATE_KEY="$PRIVATE_KEY"' in command for command in commands)
assert not any("PRIVATE_KEY=..." in command for command in commands)
PY
  then
    pass "X0T governance execute operator handoff is actionable and read-only"
  else
    fail "X0T governance execute operator handoff is actionable and read-only"
  fi
  rm -f "${tmp}"
}

run_ghost_pulse_artifact_chain_current_smoke_check() {
  local tmp
  tmp="$(mktemp)"
  if python3 scripts/ops/verify_ghost_pulse_artifact_chain.py --json >"${tmp}" 2>/dev/null \
    && python3 - "${tmp}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
artifacts = data.get("artifacts", {})
claim_boundary = data.get("claim_boundary", {})
gates = data.get("gates", {})

assert data.get("schema") == "x0tta6bl4.ghost_pulse.artifact_chain.v1"
assert data.get("decision") == "GHOST_PULSE_ARTIFACT_CHAIN_VERIFIED"
assert data.get("failures") == []
assert artifacts.get("local_evidence") == "docs/verification/GHOST_PULSE_LOCAL_EVIDENCE_LATEST.json"
assert artifacts.get("profile_matrix") == "docs/verification/GHOST_PULSE_PROFILE_MATRIX_LATEST.json"
assert artifacts.get("verification_suite") == "docs/verification/GHOST_PULSE_VERIFICATION_SUITE_LATEST.json"
assert artifacts.get("external_evidence_intake") == "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST.json"
assert artifacts.get("local_evidence_sha256")
assert artifacts.get("profile_matrix_sha256")
assert artifacts.get("verification_suite_sha256")
assert artifacts.get("external_evidence_intake_sha256")
assert claim_boundary.get("stealth_verified") is False
assert claim_boundary.get("whitelist_verified") is False
assert claim_boundary.get("production_ready") is False
assert claim_boundary.get("kernel_attach_verified") is False
for gate_name in (
    "local_evidence_verifier",
    "profile_matrix_verifier",
    "seed_replay_verifier",
    "suite_self_verifier",
    "external_evidence_intake_verifier",
    "replacement_candidates_verifier",
):
    assert gates.get(gate_name, {}).get("status") == "PASS"
PY
  then
    pass "ghost-pulse artifact chain current artifacts are internally consistent"
  else
    fail "ghost-pulse artifact chain current artifacts are internally consistent"
  fi
  rm -f "${tmp}"
}

run_ghost_pulse_proof_gate_current_smoke_check() {
  local tmp
  tmp="$(mktemp)"
  if python3 scripts/ops/verify_ghost_pulse_proof_gate.py --json >"${tmp}" 2>/dev/null \
    && python3 scripts/ops/verify_ghost_pulse_external_evidence_inventory.py --json >/dev/null 2>/dev/null \
    && python3 - "${tmp}" <<'PY'
import json
import sys

result = json.load(open(sys.argv[1], encoding="utf-8"))
claim_boundary = result.get("claim_boundary", {})
replacement_candidates = result.get("replacement_candidates", {})

assert result.get("status") == "PASS"
assert result.get("decision") in {
    "GHOST_PULSE_PROOF_INCOMPLETE",
    "GHOST_PULSE_ALL_CLAIMS_PROVEN",
}
assert replacement_candidates.get("status") == "PASS"
assert replacement_candidates.get("decision") in {
    "REPLACEMENT_CANDIDATES_READY",
    "REPLACEMENT_CANDIDATES_NOT_READY",
}
assert replacement_candidates.get("report") == "docs/verification/GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.json"
replacement_boundary = replacement_candidates.get("claim_boundary", {})
assert replacement_boundary.get("stealth_verified") is False
assert replacement_boundary.get("whitelist_verified") is False
assert replacement_boundary.get("kernel_attach_verified") is False
assert replacement_boundary.get("production_ready") is False
if result.get("decision") == "GHOST_PULSE_PROOF_INCOMPLETE":
    assert claim_boundary.get("production_ready") is False
    assert result.get("not_verified_yet")
if claim_boundary.get("production_ready") is True:
    assert result.get("decision") == "GHOST_PULSE_ALL_CLAIMS_PROVEN"
PY
  then
    pass "ghost-pulse all-claims proof gate is fail-closed"
  else
    fail "ghost-pulse all-claims proof gate is fail-closed"
  fi
  rm -f "${tmp}"
}

run_ghost_pulse_goal_state_current_smoke_check() {
  local tmp require_complete_code
  tmp="$(mktemp)"
  set +e
  python3 scripts/ops/verify_ghost_pulse_goal_state.py --require-complete --json >/dev/null 2>/dev/null
  require_complete_code=$?
  set -e
  if python3 scripts/ops/verify_ghost_pulse_goal_state.py --json >"${tmp}" 2>/dev/null \
    && python3 scripts/ops/verify_ghost_pulse_goal_state.py \
      --report docs/verification/GHOST_PULSE_GOAL_STATE_LATEST.json \
      --json >/dev/null 2>/dev/null \
    && python3 - "${tmp}" "${require_complete_code}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
require_complete_code = int(sys.argv[2])
boundary = data.get("claim_boundary", {})
pending = data.get("pending_external_evidence_claims", [])
sources = data.get("source_reports", {})

assert data.get("schema") == "x0tta6bl4.ghost_pulse.goal_state.v1"
assert data.get("status") == "PASS"
assert data.get("failures") == []
assert data.get("starter_verified_claims") == [
    "packet_capture",
    "baseline_timing_comparison",
]
assert sources.get("proof", {}).get("path") == "docs/verification/GHOST_PULSE_PROOF_GATE_LATEST.json"
assert sources.get("external_evidence_intake", {}).get("path") == (
    "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST.json"
)
assert sources.get("external_evidence_inventory", {}).get("path") == (
    "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INVENTORY_LATEST.json"
)
assert data.get("decision") in {
    "GHOST_PULSE_GOAL_STATE_GAPS_RECORDED_FAIL_CLOSED",
    "GHOST_PULSE_GOAL_STATE_ALL_CLAIMS_PROVEN",
}
if data.get("decision") == "GHOST_PULSE_GOAL_STATE_GAPS_RECORDED_FAIL_CLOSED":
    assert pending
    assert boundary.get("production_ready") is False
    assert require_complete_code == 1
else:
    assert pending == []
    assert boundary.get("production_ready") is True
    assert require_complete_code == 0
PY
  then
    pass "ghost-pulse active goal state is machine-checkable and fail-closed"
  else
    fail "ghost-pulse active goal state is machine-checkable and fail-closed"
  fi
  rm -f "${tmp}"
}

run_ghost_pulse_replacement_candidates_current_smoke_check() {
  local tmp require_ready_code
  tmp="$(mktemp)"
  set +e
  python3 scripts/ops/verify_ghost_pulse_replacement_candidates.py --require-ready --json >/dev/null 2>/dev/null
  require_ready_code=$?
  set -e
  if python3 scripts/ops/verify_ghost_pulse_replacement_candidates.py --json >"${tmp}" 2>/dev/null \
    && python3 scripts/ops/verify_ghost_pulse_replacement_candidates.py \
      --report docs/verification/GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.json \
      --json >/dev/null 2>/dev/null \
    && python3 - "${tmp}" "${require_ready_code}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
require_ready_code = int(sys.argv[2])
claim_boundary = data.get("claim_boundary", {})
replacement_required = data.get("replacement_required", [])
ready = data.get("ready", [])
not_ready = data.get("not_ready", [])
rows = data.get("rows", [])

assert data.get("schema") == "x0tta6bl4.ghost_pulse.replacement_candidate_preflight.v1"
assert data.get("status") == "PASS"
assert data.get("failures") == []
assert data.get("gap_audit_failures") == []
assert data.get("decision") in {
    "REPLACEMENT_CANDIDATES_READY",
    "REPLACEMENT_CANDIDATES_NOT_READY",
}
assert claim_boundary.get("stealth_verified") is False
assert claim_boundary.get("whitelist_verified") is False
assert claim_boundary.get("kernel_attach_verified") is False
assert claim_boundary.get("production_ready") is False
assert len(rows) == len(replacement_required)
if data.get("decision") == "REPLACEMENT_CANDIDATES_NOT_READY":
    assert not_ready
    assert require_ready_code == 1
else:
    assert ready == replacement_required
    assert not not_ready
    assert require_ready_code == 0
PY
  then
    pass "ghost-pulse replacement candidates are explicitly fail-closed"
  else
    fail "ghost-pulse replacement candidates are explicitly fail-closed"
  fi
  rm -f "${tmp}"
}

run_ghost_pulse_external_evidence_intake_current_smoke_check() {
  local tmp require_ready_code
  tmp="$(mktemp)"
  set +e
  python3 scripts/ops/verify_ghost_pulse_external_evidence_intake.py --require-all-ready --json >/dev/null 2>/dev/null
  require_ready_code=$?
  set -e
  if python3 scripts/ops/verify_ghost_pulse_external_evidence_intake.py --json >"${tmp}" 2>/dev/null \
    && python3 scripts/ops/verify_ghost_pulse_external_evidence_intake.py \
      --report docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST.json \
      --json >/dev/null 2>/dev/null \
    && python3 - "${tmp}" "${require_ready_code}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
require_ready_code = int(sys.argv[2])
claim_boundary = data.get("claim_boundary", {})
ready = data.get("ready", [])
not_ready = data.get("not_ready", [])

assert data.get("schema") == "x0tta6bl4.ghost_pulse.external_evidence_intake.v1"
assert data.get("status") == "PASS"
assert data.get("failures") == []
assert data.get("decision") in {
    "EXTERNAL_EVIDENCE_INTAKE_ACTION_REQUIRED",
    "EXTERNAL_EVIDENCE_INTAKE_READY_NOT_WRITTEN",
}
assert data.get("preflight") == "docs/verification/GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.json"
assert data.get("preflight_verification", {}).get("status") == "PASS"
assert claim_boundary.get("stealth_verified") is False
assert claim_boundary.get("whitelist_verified") is False
assert claim_boundary.get("kernel_attach_verified") is False
assert claim_boundary.get("production_ready") is False
if data.get("decision") == "EXTERNAL_EVIDENCE_INTAKE_ACTION_REQUIRED":
    assert not_ready
    assert require_ready_code == 1
else:
    assert ready
    assert not not_ready
    assert require_ready_code == 0
PY
  then
    pass "ghost-pulse external evidence intake is explicitly fail-closed"
  else
    fail "ghost-pulse external evidence intake is explicitly fail-closed"
  fi
  rm -f "${tmp}"
}

# =============================================================================
echo ""
echo "========================================================="
echo "  x0tta6bl4 v1.1 — Verification Entrypoint"
echo "  $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "========================================================="
echo ""

# -- read agent coordination state if available -------------------------------
if [[ -f "${ROOT_DIR}/.agent-coord/state.json" ]]; then
  NOT_YET=$(python3 -c "
import json
s = json.load(open('${ROOT_DIR}/.agent-coord/state.json'))
items = s.get('global_not_verified_yet', [])
print(f'  [{len(items)} items still NOT VERIFIED YET — see .agent-coord/state.json]')
" 2>/dev/null || true)
  echo -e "${CYN}[coord] Agent state found.${RST} ${NOT_YET}"
  echo ""
fi

# -- 1. YAML / config syntax --------------------------------------------------
echo -e "${CYN}[1/12] YAML and config syntax${RST}"

run_check "gitlab-ci.yml parses" \
  python3 -c 'import yaml; yaml.safe_load(open(".gitlab-ci.yml")); print("ok")'

run_check "security/sbom/gitlab-ci-sbom.yml parses" \
  python3 -c 'import yaml; yaml.safe_load(open("security/sbom/gitlab-ci-sbom.yml")); print("ok")'

run_check "charts/multi-tenant/values-enterprise.yaml parses" \
  python3 -c 'import yaml; yaml.safe_load(open("charts/multi-tenant/values-enterprise.yaml")); print("ok")'

run_check "charts/x0tta6bl4-commercial/values-enterprise.yaml parses" \
  python3 -c 'import yaml; yaml.safe_load(open("charts/x0tta6bl4-commercial/values-enterprise.yaml")); print("ok")'

# -- 2. Helm lint -------------------------------------------------------------
echo ""
echo -e "${CYN}[2/12] Helm chart lint${RST}"

if command -v helm >/dev/null 2>&1; then
  for chart in charts/api-gateway charts/observability charts/x0tta6bl4-commercial; do
    if [[ -d "${chart}" ]]; then
      run_helm_lint_check "${chart}"
    fi
  done
else
  skip "helm lint — helm not in PATH; use charts/render-in-docker.sh"
fi

# -- 3. eBPF loader build -----------------------------------------------------
echo ""
echo -e "${CYN}[3/12] eBPF loader build${RST}"

if command -v go >/dev/null 2>&1; then
  run_ebpf_build_check

  run_check "CO-RE generation path wired (make -n)" \
    bash -c 'make -n -f ebpf/prod/Makefile.bpf generate 2>&1 | grep -q "bpf2go"'

  mkdir -p "${ROOT_DIR}/.tmp/go-build"
  run_check "go test ./edge/5g/... focused package tests" \
    env GOCACHE="${ROOT_DIR}/.tmp/go-build" GOTOOLCHAIN=local go test ./edge/5g/...
else
  skip "go build ./ebpf/prod — go not in PATH"
  skip "CO-RE generation path — go not in PATH"
  skip "go test ./edge/5g/... focused package tests — go not in PATH"
fi

# -- 4. Kernel and BTF --------------------------------------------------------
echo ""
echo -e "${CYN}[4/12] Kernel and BTF availability${RST}"

python3 - <<'PY' 2>/dev/null && pass "kernel >= 6.1" || fail "kernel >= 6.1"
import platform, re, sys
m = re.match(r"(\d+)\.(\d+)", platform.release())
if not m: sys.exit(1)
maj, min_ = map(int, m.groups())
sys.exit(0 if (maj, min_) >= (6, 1) else 1)
PY

if [[ -f /sys/kernel/btf/vmlinux ]]; then
  pass "BTF present at /sys/kernel/btf/vmlinux"
else
  fail "BTF not present at /sys/kernel/btf/vmlinux"
fi

# -- 5. Python unit tests -----------------------------------------------------
echo ""
echo -e "${CYN}[5/12] Python unit tests${RST}"

if [[ "${FAST}" -eq 1 ]]; then
  skip "Python unit tests (skipped with --fast)"
else
  if command -v python3 >/dev/null 2>&1 && python3 -c 'import pytest' 2>/dev/null; then
    # Run once; capture output; derive pass/fail and count from the same run
    PYTEST_OUT=$(python3 -m pytest \
        tests/unit/dao/test_dao_executor_spine_unit.py \
        tests/unit/dao/test_governance.py \
        tests/unit/dao/test_governance_contract_spine_unit.py \
        tests/unit/dao/test_governance_spine_unit.py \
        tests/unit/dao/test_token_bridge.py \
        tests/unit/dao/test_token_bridge_spine_unit.py \
        tests/unit/dao/test_token_bridge_unit.py \
        tests/unit/dao/test_token_rewards_unit.py \
        tests/unit/dao/test_x0t_bridge_config.py \
        tests/unit/dao/test_x0t_contract_build_verification.py \
        tests/unit/dao/test_x0t_contract_readiness.py \
        tests/unit/test_integration_completion_audit.py \
        tests/unit/test_integration_current_evidence_rollup.py \
        tests/unit/test_integration_semantic_production_blocker_queue.py \
        tests/unit/test_integration_raw_evidence_inventory.py \
        tests/unit/test_integration_evidence_source_candidates.py \
        tests/unit/test_integration_operator_bundle_identity.py \
        tests/unit/test_integration_operator_bundle_gate.py \
        tests/unit/test_integration_operator_evidence_packet.py \
        tests/unit/test_integration_production_evidence_import.py \
        tests/unit/test_integration_production_evidence_replacement_passport.py \
        tests/unit/test_ops_production_evidence_validation_wrappers.py \
        tests/unit/scripts/test_apply_operator_bundle_identity_patch.py \
        tests/unit/test_integration_required_evidence_consistency.py \
        tests/unit/test_integration_rollup_approval_contract.py \
        tests/unit/test_integration_production_input_return_acceptance.py \
        tests/unit/test_integration_production_input_return_packet.py \
        tests/unit/test_integration_production_input_bundle_stage.py \
        tests/unit/test_integration_production_input_pipeline.py \
        tests/unit/test_integration_scaffold_retained_raw_prefill.py \
        tests/unit/test_integration_source_runtime_surface.py \
        tests/unit/test_integration_current_shard_stale_guard.py \
        tests/unit/test_integration_stale_roadmap_audit_entrypoint_check.py \
        tests/unit/test_integration_operator_bundle_secret_scan.py \
        tests/unit/test_integration_objective_coverage_audit.py \
        tests/unit/test_integration_goal_completion_audit.py \
        tests/unit/test_integration_completion_gate_runner.py \
        tests/unit/test_integration_production_closeout_review.py \
        tests/unit/test_integration_production_gap_index.py \
        tests/unit/test_integration_production_evidence_intake.py \
        tests/unit/test_integration_production_raw_evidence_readiness.py \
        tests/unit/test_integration_production_raw_evidence_collector_gate.py \
        tests/unit/test_integration_production_raw_evidence_entrypoint.py \
        tests/unit/test_integration_production_raw_evidence_semantics.py \
        tests/unit/test_integration_production_raw_evidence_pipeline.py \
        tests/unit/test_integration_production_raw_evidence_operator_packet.py \
        tests/unit/scripts/test_audit_production_grade_goal.py \
        tests/unit/test_integration_evidence_readiness.py \
        tests/unit/test_x0t_governance_execute_readiness.py \
        tests/unit/test_x0t_governance_execute_proposal_script.py \
        tests/unit/test_x0t_governance_execute_handoff.py \
        tests/unit/test_integration_external_settlement.py \
        tests/unit/test_integration_external_settlement_operator_handoff.py \
        tests/unit/test_integration_rollout_provenance.py \
        tests/unit/test_integration_spine.py \
        tests/unit/scripts/test_verify_entrypoint_static_duplicate_guard.py \
        tests/unit/scripts/test_run_ghost_pulse_verification_suite.py \
        tests/unit/scripts/test_verify_ghost_pulse_artifact_chain.py \
        tests/unit/scripts/test_verify_ghost_pulse_rng_replay.py \
        tests/unit/scripts/test_verify_ghost_pulse_verification_suite.py \
        tests/unit/network/test_mptcp_manager_spine_unit.py \
        tests/unit/network/test_pulse_transport_replay_unit.py \
        tests/unit/security/test_dependency_security_pins_unit.py \
        tests/unit/security/spiffe/test_spire_agent_manager_spine_unit.py \
        tests/unit/security/spiffe/test_spire_server_client_spine_unit.py \
        tests/unit/network/test_mesh_vpn_bridge_unit.py \
        tests/unit/self_healing/test_recovery_actions_unit.py \
        tests/unit/self_healing/test_pqc_zero_trust_healer_unit.py \
        tests/unit/self_healing/test_mape_k_spiffe_integration_unit.py \
        tests/unit/self_healing/test_ebpf_anomaly_detector_unit.py \
        tests/unit/server/test_ghost_server_unit.py \
        tests/unit/api/test_maas_governance_spine_unit.py \
        tests/unit/swarm/test_pbft_spine_unit.py \
        tests/unit/swarm/test_swarm_mapek_spine_unit.py \
        tests/unit/api/test_maas_marketplace_unit.py \
        tests/dao/test_token_bridge.py \
        tests/unit/services/test_marketplace_events_unit.py \
        tests/unit/services/test_marketplace_janitor_unit.py \
        tests/unit/services/test_marketplace_settlement_unit.py \
        tests/unit/services/test_pqc_rotator_service_unit.py \
        tests/unit/services/test_reward_events_unit.py \
        tests/unit/services/test_share_to_earn_service_unit.py \
        tests/unit/services/test_service_event_identity_unit.py \
        tests/unit/scripts/test_validate_enterprise_workflows_unit.py \
        tests/unit/mesh/test_telemetry_collector_unit.py \
        tests/benchmarks/test_api_memory_profile.py \
        --no-cov -q --tb=no 2>&1) && PYTEST_EXIT=0 || PYTEST_EXIT=$?
    COUNT=$(python3 -c 'import re, sys; match = re.search(r"([0-9]+ passed)", sys.stdin.read()); print(match.group(1) if match else "")' <<<"${PYTEST_OUT}")
    if [[ "${PYTEST_EXIT}" -eq 0 ]] && [[ -n "${COUNT}" ]]; then
      pass "Python unit tests (${COUNT})"
    else
      fail "Python unit tests"
    fi
  else
    skip "Python unit tests — pytest not available"
  fi
fi

# -- 6. Integration-spine current artifact smoke ------------------------------
echo ""
echo -e "${CYN}[6/12] Integration-spine current artifact smoke${RST}"

run_check "verify-v1.1 static duplicate guard" \
  python3 scripts/ops/check_verify_entrypoint_duplicates.py scripts/verify-v1.1.sh

run_ghost_pulse_artifact_chain_current_smoke_check
run_ghost_pulse_proof_gate_current_smoke_check
run_ghost_pulse_goal_state_current_smoke_check
run_ghost_pulse_replacement_candidates_current_smoke_check
run_ghost_pulse_external_evidence_intake_current_smoke_check
run_code_wiring_current_smoke_check
run_operator_packet_current_smoke_check
run_operator_packet_index_current_smoke_check
run_external_settlement_preflight_current_smoke_check
run_external_settlement_scaffold_current_smoke_check
run_external_settlement_template_retained_rejection_smoke_check
run_external_settlement_operator_handoff_current_smoke_check
run_production_input_return_packet_current_smoke_check
run_operator_bundle_secret_scan_current_smoke_check
run_live_rollout_image_provenance_scaffold_current_smoke_check
run_production_raw_evidence_template_pack_current_smoke_check
run_production_raw_evidence_readiness_current_smoke_check
run_production_raw_evidence_semantics_current_smoke_check
run_production_raw_evidence_pipeline_current_smoke_check
run_production_raw_evidence_operator_packet_current_smoke_check
run_production_grade_goal_audit_current_smoke_check
run_production_raw_evidence_template_rejection_smoke_check
run_live_rollout_image_template_bundle_rejection_smoke_check
run_scaffold_retained_raw_prefill_current_smoke_check
run_source_runtime_surface_current_smoke_check
run_stale_roadmap_entrypoint_triage_smoke_check
run_rollout_provenance_current_smoke_check
run_current_evidence_rollup_current_smoke_check
run_semantic_queue_current_smoke_check
run_raw_evidence_inventory_current_smoke_check
run_operator_bundle_identity_current_smoke_check
run_operator_bundle_identity_patch_current_smoke_check
run_replacement_passport_current_smoke_check
run_production_evidence_import_current_smoke_check
run_production_input_return_acceptance_current_smoke_check
run_production_input_bundle_stage_current_smoke_check
run_production_input_pipeline_current_smoke_check
run_objective_coverage_audit_current_smoke_check
run_goal_completion_audit_current_smoke_check
run_required_evidence_consistency_current_smoke_check
run_rollup_approval_contract_current_smoke_check
run_production_closeout_review_current_smoke_check
run_completion_audit_current_smoke_check
run_production_gap_index_current_smoke_check
run_completion_gate_runner_current_smoke_check
run_x0t_bridge_config_current_smoke_check
run_x0t_contract_build_verification_artifact_smoke_check
run_x0t_contract_readiness_current_smoke_check
run_x0t_governance_execute_readiness_artifact_smoke_check
run_x0t_governance_execute_handoff_smoke_check
run_current_shard_stale_guard_smoke_check

# -- 7. Coordination contract sanity ------------------------------------------
echo ""
echo -e "${CYN}[7/12] Coordination contract sanity${RST}"

run_check "coordination docs do not drift to manual status-board mode" \
  bash scripts/agents/check_coordination_contract.sh

# -- 8. Truth-surface claim hygiene -------------------------------------------
echo ""
echo -e "${CYN}[8/12] Truth-surface claim hygiene${RST}"

run_check "authoritative claim surface has no active high-risk claims" \
  bash scripts/agent-coord.sh claim_hygiene_scan --zone authoritative --fail-on-active

run_check "active public claim surface has no active high-risk claims" \
  bash scripts/agent-coord.sh claim_hygiene_scan --zone active_claim_surface --fail-on-active

run_check "architecture claim surface has no active high-risk claims" \
  bash scripts/agent-coord.sh claim_hygiene_scan --zone architecture --fail-on-active

run_check "cross-plane proof-gate retained artifact validates" \
  bash -c 'python3 scripts/ops/run_cross_plane_proof_gate.py --output-json .tmp/validation-shards/cross-plane-proof-gate-current.json >/dev/null && python3 scripts/ops/verify_cross_plane_proof_gate_retention.py --require-valid >/dev/null'

# -- 9. SOC2 playbook sanity --------------------------------------------------
echo ""
echo -e "${CYN}[9/12] SOC2 / compliance artifacts${RST}"

run_check "compliance/soc2/playbook.md contains SEV-1 definition" \
  grep -q "SEV-1" compliance/soc2/playbook.md

run_check "compliance/soc2/evidence-matrix.md exists" \
  test -f compliance/soc2/evidence-matrix.md

run_check "docs/verification/v1.1-hardening-status.md exists" \
  test -f docs/verification/v1.1-hardening-status.md

run_check "docs/verification/operator-live-validation-checklist.md exists" \
  test -f docs/verification/operator-live-validation-checklist.md

run_benchmark_harness_check

# -- 10. Docker available for containerised paths -----------------------------
echo ""
echo -e "${CYN}[10/12] Container runtime (Docker)${RST}"

if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  DOCKER_VER=$(docker --version 2>/dev/null | head -1)
  pass "Docker daemon reachable (${DOCKER_VER})"
  # These paths exist and are runnable but not executed here
  ci  "SBOM generation (security/sbom/run-local-sbom-check.sh full --tool-mode docker)"
  ci  "Cosign mock signing (security/sbom/verify-cosign-rekor.sh --mode mock --tool-mode docker)"
  ci  "Helm render containerised (charts/render-in-docker.sh)"
else
  skip "Docker daemon not reachable in this execution context — containerised paths unavailable here"
fi

# -- 11. Environment-blocked checks -------------------------------------------
echo ""
echo -e "${CYN}[11/12] Checks blocked by environment${RST}"

skip "Live XDP attach — requires root + real NIC (sudo ebpf/prod/verify-local.sh --live-attach)"
skip "PPS benchmark >5M — requires root + pktgen (RUN_BENCH=1 IFACE=eth0 ebpf/prod/benchmark-harness.sh)"
skip "Rekor transparency-log upload — requires SIGSTORE_ID_TOKEN (CI only)"
skip "5G UPF live validation — requires UERANSIM hardware/simulation cluster"
skip "LoRa field range test — requires SX1303 hardware"
skip "DP-SGD real noise validation — requires lab setup"
skip "Playwright E2E — requires running stack"
skip "k6 load test — requires running API endpoint"

# -- 12. RC1 Consistency Gate -------------------------------------------------
echo ""
echo -e "${CYN}[12/12] RC1 Consistency Gate${RST}"

run_check "release documents are synchronized" \
  python3 scripts/ops/check_release_consistency.py
# =============================================================================
echo ""
echo "========================================================="
echo "  SUMMARY"
echo "========================================================="
echo ""

if [[ ${#VERIFIED_HERE[@]} -gt 0 ]]; then
  echo -e "${GRN}VERIFIED HERE (${#VERIFIED_HERE[@]})${RST}"
  for item in "${VERIFIED_HERE[@]}"; do echo "  + ${item}"; done
  echo ""
fi

if [[ ${#VERIFIED_VIA_CI[@]} -gt 0 ]]; then
  echo -e "${YLW}VERIFIED VIA SCRIPT/CI (${#VERIFIED_VIA_CI[@]})${RST}"
  for item in "${VERIFIED_VIA_CI[@]}"; do echo "  ~ ${item}"; done
  echo ""
fi

if [[ ${#NOT_VERIFIED[@]} -gt 0 ]]; then
  echo -e "${CYN}NOT VERIFIED YET (${#NOT_VERIFIED[@]})${RST}"
  for item in "${NOT_VERIFIED[@]}"; do echo "  - ${item}"; done
  echo ""
fi

if [[ ${#FAILED[@]} -gt 0 ]]; then
  echo -e "${RED}FAILED (${#FAILED[@]})${RST}"
  for item in "${FAILED[@]}"; do echo "  ! ${item}"; done
  echo ""
fi

# Compact table
printf "  %-28s %s\n" "VERIFIED HERE:"         "${#VERIFIED_HERE[@]} checks passed in this environment"
printf "  %-28s %s\n" "VERIFIED VIA SCRIPT/CI:" "${#VERIFIED_VIA_CI[@]} reproducible scripts (not run here)"
printf "  %-28s %s\n" "NOT VERIFIED YET:"       "${#NOT_VERIFIED[@]} blocked by hardware / credentials"
if [[ ${#FAILED[@]} -gt 0 ]]; then
  printf "  %-28s %s\n" "FAILED:" "${#FAILED[@]} checks — fix before claiming verification"
fi
echo ""
echo -e "${RED}Do not claim as publicly verified:${RST}"
echo "  - High PPS throughput (>1M): RC1 empirical baseline is 142k TX / 49 RX PPS"
echo "  - MTTR / uptime: derived from simulated self-healing, not production traffic"
echo "  - GNN accuracy: 94% is a training-set figure, not production measurement"
echo "  - Rekor inclusion: requires SIGSTORE_ID_TOKEN; CI only"
echo "  - 5G / LoRa / DP-SGD: simulated or partial (SCTP/PFCP only); not field-validated"
echo ""

# -- optional JSON output -----------------------------------------------------
if [[ "${JSON}" -eq 1 ]]; then
  # Write arrays to temp files to avoid shell quoting issues in here-doc
  _TMP=$(mktemp -d)
  printf '%s\n' "${VERIFIED_HERE[@]+"${VERIFIED_HERE[@]}"}"  > "${_TMP}/vh.txt"
  printf '%s\n' "${VERIFIED_VIA_CI[@]+"${VERIFIED_VIA_CI[@]}"}" > "${_TMP}/vc.txt"
  printf '%s\n' "${NOT_VERIFIED[@]+"${NOT_VERIFIED[@]}"}"     > "${_TMP}/nv.txt"
  printf '%s\n' "${FAILED[@]+"${FAILED[@]}"}"                 > "${_TMP}/fa.txt"
  python3 - "${_TMP}" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" <<'PY'
import json, sys, pathlib
d, ts = pathlib.Path(sys.argv[1]), sys.argv[2]
def read_list(path):
    lines = path.read_text().splitlines()
    return [l for l in lines if l.strip()]
data = {
    "timestamp":        ts,
    "verified_here":    read_list(d / "vh.txt"),
    "verified_via_ci":  read_list(d / "vc.txt"),
    "not_verified_yet": read_list(d / "nv.txt"),
    "failed":           read_list(d / "fa.txt"),
}
print(json.dumps(data, indent=2))
PY
  rm -rf "${_TMP}"
fi

# -- log result to agent coordination state ------------------------------------
if [[ -f "${ROOT_DIR}/scripts/agent-coord.sh" ]]; then
  bash "${ROOT_DIR}/scripts/agent-coord.sh" log "${VERIFY_AGENT_NAME}" "verify_run" \
    "{\"verified_here\": ${#VERIFIED_HERE[@]}, \"failed\": ${#FAILED[@]}, \"fast\": ${FAST}}" \
    2>/dev/null || true
fi

# exit non-zero if any check failed
[[ ${#FAILED[@]} -eq 0 ]] || exit 1
