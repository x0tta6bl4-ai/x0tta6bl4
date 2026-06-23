#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
NL_HOST="${NL_HOST:-nl}"
REVIEW_JSON_OUT="${REVIEW_JSON_OUT:-${PROJECT_ROOT}/nl-diagnostics/nl-no-progress-nudge-review-latest.json}"
REFRESH_CMD="${REFRESH_CMD:-${PROJECT_ROOT}/scripts/refresh_nl_vpn_readonly_evidence.sh}"
VPN_STATUS_CMD="${VPN_STATUS_CMD:-${PROJECT_ROOT}/scripts/vpn_status.sh}"
SSH_CMD="${SSH_CMD:-ssh}"

SSH_OPTS=(
  -o BatchMode=yes
  -o ConnectTimeout=10
)

if ! command -v jq >/dev/null 2>&1; then
  printf 'jq is required for no-progress nudge review\n' >&2
  exit 1
fi

printf '[refresh]\n' >&2
bash "${REFRESH_CMD}" >/dev/null

status_json="$(bash "${VPN_STATUS_CMD}" --json)"

action="$(jq -r '.next_safe_action.action // "unknown"' <<<"${status_json}")"
reason="$(jq -r '.next_safe_action.reason // ""' <<<"${status_json}")"
allowed="$(jq -r '.next_safe_action.user_message_allowed_after_review // false' <<<"${status_json}")"
candidate_count="$(jq -r '.next_safe_action.no_progress_candidate_count // 0' <<<"${status_json}")"
earliest_mutation_at="$(jq -r '.next_safe_action.earliest_mutation_at // ""' <<<"${status_json}")"
earliest_mutation_seconds_until="$(jq -r '.next_safe_action.earliest_mutation_seconds_until // 0' <<<"${status_json}")"
overall_status="$(jq -r '.overall_status // "unknown"' <<<"${status_json}")"
user_status="$(jq -r '.user_connectivity.status // "unknown"' <<<"${status_json}")"
transport_status="$(jq -r '.transport_usage.status // "unknown"' <<<"${status_json}")"
transport_restart_relevant="$(jq -r '.transport_usage.summary.restart_relevant // false' <<<"${status_json}")"
cooldown_active="$(jq -r '.next_safe_action.cooldown_active // false' <<<"${status_json}")"
automatic_restart_allowed="$(jq -r '.next_safe_action.automatic_restart_allowed // false' <<<"${status_json}")"
immediate_readonly_actions="$(jq -c '.next_safe_action.immediate_readonly_actions // []' <<<"${status_json}")"
deferred_readonly_actions="$(jq -c '.next_safe_action.deferred_readonly_actions // []' <<<"${status_json}")"
blocked_actions="$(jq -c '.next_safe_action.blocked_actions // []' <<<"${status_json}")"
blockers="$(jq -c '.user_connectivity.blockers // []' <<<"${status_json}")"

ready_blockers=()
if [[ "${action}" != "review_and_send_no_progress_nudge" ]]; then
  ready_blockers+=("action_not_review_and_send_no_progress_nudge")
fi
if [[ "${allowed}" != "true" ]]; then
  ready_blockers+=("user_message_not_allowed_after_review")
fi
if [[ ! "${candidate_count}" =~ ^[0-9]+$ ]]; then
  ready_blockers+=("no_progress_candidate_count_invalid")
elif [[ "${candidate_count}" -le 0 ]]; then
  ready_blockers+=("no_progress_candidate_count_zero")
fi
if [[ "${cooldown_active}" == "true" ]]; then
  ready_blockers+=("cooldown_active")
fi
if [[ "${transport_restart_relevant}" != "false" ]]; then
  ready_blockers+=("transport_restart_relevant")
fi
if [[ "${immediate_readonly_actions}" != "[]" ]]; then
  ready_blockers+=("immediate_readonly_actions_pending")
fi

ready=false
if [[ "${#ready_blockers[@]}" -eq 0 ]]; then
  ready=true
fi

hash_json='{}'
hash_collection_status="not_required"
hash_collection_exit_code=0
hash_collection_error_sha256=""
hash_collection_error_size_bytes=0
if [[ "${ready}" == "true" ]]; then
  hash_collection_status="success"
  set +e
  hash_output="$(
    "${SSH_CMD}" "${SSH_OPTS[@]}" "${NL_HOST}" '
set -euo pipefail
jq -n \
  --arg packet "$(sha256sum /var/lib/ghost-access/legacy-migration/latest.json | cut -d " " -f1)" \
  --arg dry_run "$(sha256sum /var/lib/ghost-access/legacy-migration/no-progress-nudge-dry-run.json | cut -d " " -f1)" \
  --arg subscription_payload "$(sha256sum /var/lib/ghost-access/subscription-payload/latest.json | cut -d " " -f1)" \
  --arg transport_usage "$(sha256sum /var/lib/ghost-access/transport-usage/latest.json | cut -d " " -f1)" \
  --arg replies "$(sha256sum /var/lib/ghost-access/legacy-migration/replies.json | cut -d " " -f1)" \
  "{packet: \$packet, dry_run: \$dry_run, subscription_payload: \$subscription_payload, transport_usage: \$transport_usage, replies: \$replies}"
' 2>&1
  )"
  hash_collection_exit_code=$?
  set -e
  if [[ "${hash_collection_exit_code}" -ne 0 ]] || ! jq -e 'type == "object"' >/dev/null 2>&1 <<<"${hash_output}"; then
    ready=false
    reason="remote hash collection failed before no-progress nudge review"
    hash_collection_status="failed"
    hash_collection_error_size_bytes="${#hash_output}"
    hash_collection_error_sha256="$(printf '%s' "${hash_output}" | sha256sum | cut -d ' ' -f1)"
    ready_blockers+=("hash_collection_failed")
    hash_json='{}'
  else
    hash_json="${hash_output}"
  fi
fi

if [[ "${#ready_blockers[@]}" -eq 0 ]]; then
  ready_blockers_json="[]"
else
  ready_blockers_json="$(printf '%s\n' "${ready_blockers[@]}" | jq -Rsc 'split("\n")[:-1]')"
fi

review_json="$(
jq -n \
  --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg overall_status "${overall_status}" \
  --arg action "${action}" \
  --arg reason "${reason}" \
  --arg user_status "${user_status}" \
  --arg transport_status "${transport_status}" \
  --arg earliest_mutation_at "${earliest_mutation_at}" \
  --arg hash_collection_status "${hash_collection_status}" \
  --arg hash_collection_error_sha256 "${hash_collection_error_sha256}" \
  --argjson ready "${ready}" \
  --argjson user_message_allowed_after_review "${allowed}" \
  --argjson no_progress_candidate_count "${candidate_count}" \
  --argjson cooldown_active "${cooldown_active}" \
  --argjson earliest_mutation_seconds_until "${earliest_mutation_seconds_until}" \
  --argjson automatic_restart_allowed "${automatic_restart_allowed}" \
  --argjson hash_collection_exit_code "${hash_collection_exit_code}" \
  --argjson hash_collection_error_size_bytes "${hash_collection_error_size_bytes}" \
  --argjson transport_restart_relevant "${transport_restart_relevant}" \
  --argjson ready_blockers "${ready_blockers_json}" \
  --argjson immediate_readonly_actions "${immediate_readonly_actions}" \
  --argjson deferred_readonly_actions "${deferred_readonly_actions}" \
  --argjson blocked_actions "${blocked_actions}" \
  --argjson blockers "${blockers}" \
  --argjson hashes "${hash_json}" \
  '{
    source: "scripts/review_nl_no_progress_nudge.sh",
    generated_at: $generated_at,
    ready: $ready,
    ready_blockers: $ready_blockers,
    overall_status: $overall_status,
    action: $action,
    reason: $reason,
    user_status: $user_status,
    user_message_allowed_after_review: $user_message_allowed_after_review,
    no_progress_candidate_count: $no_progress_candidate_count,
    earliest_mutation_at: $earliest_mutation_at,
    earliest_mutation_seconds_until: $earliest_mutation_seconds_until,
    cooldown_active: $cooldown_active,
    automatic_restart_allowed: $automatic_restart_allowed,
    hash_collection_status: $hash_collection_status,
    hash_collection_exit_code: $hash_collection_exit_code,
    hash_collection_error_sha256: $hash_collection_error_sha256,
    hash_collection_error_size_bytes: $hash_collection_error_size_bytes,
    transport_status: $transport_status,
    transport_restart_relevant: $transport_restart_relevant,
    immediate_readonly_actions: $immediate_readonly_actions,
    deferred_readonly_actions: $deferred_readonly_actions,
    blocked_actions: $blocked_actions,
    blockers: $blockers,
    expected_hashes: $hashes
  }'
)"

mkdir -p "$(dirname "${REVIEW_JSON_OUT}")"
tmp_json="${REVIEW_JSON_OUT}.tmp"
printf '%s\n' "${review_json}" >"${tmp_json}"
mv "${tmp_json}" "${REVIEW_JSON_OUT}"
printf '%s\n' "${review_json}"
