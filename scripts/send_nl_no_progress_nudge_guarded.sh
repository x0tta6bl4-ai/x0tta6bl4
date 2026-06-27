#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
NL_HOST="${NL_HOST:-nl}"
CONFIRM_NL_NO_PROGRESS_NUDGE="${CONFIRM_NL_NO_PROGRESS_NUDGE:-}"
LOCAL_SEND_OUT="${LOCAL_SEND_OUT:-${PROJECT_ROOT}/nl-diagnostics/nl-legacy-no-progress-nudge-latest.json}"
LOCAL_ATTEMPT_OUT="${LOCAL_ATTEMPT_OUT:-${PROJECT_ROOT}/nl-diagnostics/nl-no-progress-nudge-guarded-send-latest.json}"
REVIEW_CMD="${REVIEW_CMD:-${PROJECT_ROOT}/scripts/review_nl_no_progress_nudge.sh}"
SSH_CMD="${SSH_CMD:-ssh}"

SSH_OPTS=(
  -o BatchMode=yes
  -o ConnectTimeout=10
)

if ! command -v jq >/dev/null 2>&1; then
  printf 'jq is required for guarded no-progress nudge send\n' >&2
  exit 1
fi

write_attempt_result() {
  local result_json="$1"
  mkdir -p "$(dirname "${LOCAL_ATTEMPT_OUT}")"
  printf '%s\n' "${result_json}" >"${LOCAL_ATTEMPT_OUT}"
  printf '%s\n' "${result_json}"
}

set +e
review_json="$(bash "${REVIEW_CMD}")"
review_exit_code=$?
set -e
review_output_size_bytes="${#review_json}"
review_output_sha256="$(printf '%s' "${review_json}" | sha256sum | cut -d ' ' -f1)"

if [[ "${review_exit_code}" -ne 0 ]]; then
  result_json="$(
  jq -n \
    --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --arg local_attempt_out "${LOCAL_ATTEMPT_OUT}" \
    --arg review_output_sha256 "${review_output_sha256}" \
    --argjson review_exit_code "${review_exit_code}" \
    --argjson review_output_size_bytes "${review_output_size_bytes}" \
    '{
      source: "scripts/send_nl_no_progress_nudge_guarded.sh",
      generated_at: $generated_at,
      applied: false,
      status: "review_failed",
      reason: "review guard failed before guarded send",
      local_attempt_out: $local_attempt_out,
      review_exit_code: $review_exit_code,
      review_output_sha256: $review_output_sha256,
      review_output_size_bytes: $review_output_size_bytes
    }'
  )"
  write_attempt_result "${result_json}"
  exit "${review_exit_code}"
fi

if ! jq -e 'type == "object"' >/dev/null 2>&1 <<<"${review_json}"; then
  result_json="$(
  jq -n \
    --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --arg local_attempt_out "${LOCAL_ATTEMPT_OUT}" \
    --arg review_output_sha256 "${review_output_sha256}" \
    --argjson review_exit_code "${review_exit_code}" \
    --argjson review_output_size_bytes "${review_output_size_bytes}" \
    '{
      source: "scripts/send_nl_no_progress_nudge_guarded.sh",
      generated_at: $generated_at,
      applied: false,
      status: "review_output_invalid",
      reason: "review guard returned non-json output before guarded send",
      local_attempt_out: $local_attempt_out,
      review_exit_code: $review_exit_code,
      review_output_sha256: $review_output_sha256,
      review_output_size_bytes: $review_output_size_bytes
    }'
  )"
  write_attempt_result "${result_json}"
  exit 5
fi

ready="$(jq -r '.ready // false' <<<"${review_json}")"
ready_blocker_count="$(jq -r 'if ((.ready_blockers // []) | type) == "array" then ((.ready_blockers // []) | length) else 1 end' <<<"${review_json}")"
review_action="$(jq -r '.action // ""' <<<"${review_json}")"
review_allowed="$(jq -r '.user_message_allowed_after_review // false' <<<"${review_json}")"
review_cooldown_active="$(jq -r '.cooldown_active // false' <<<"${review_json}")"
review_automatic_restart_allowed="$(jq -r '.automatic_restart_allowed // false' <<<"${review_json}")"
review_transport_restart_relevant="$(jq -r '.transport_restart_relevant // false' <<<"${review_json}")"
review_hash_collection_status="$(jq -r '.hash_collection_status // ""' <<<"${review_json}")"
review_hash_collection_exit_code="$(jq -r '.hash_collection_exit_code // -1' <<<"${review_json}")"
review_immediate_readonly_count="$(
  jq -r 'if ((.immediate_readonly_actions // []) | type) == "array" then ((.immediate_readonly_actions // []) | length) else -1 end' <<<"${review_json}"
)"
review_invariant_blockers=()
if [[ "${ready}" == "true" ]]; then
  if [[ "${review_action}" != "review_and_send_no_progress_nudge" ]]; then
    review_invariant_blockers+=("action_not_review_and_send_no_progress_nudge")
  fi
  if [[ "${review_allowed}" != "true" ]]; then
    review_invariant_blockers+=("user_message_not_allowed_after_review")
  fi
  if [[ "${review_cooldown_active}" != "false" ]]; then
    review_invariant_blockers+=("cooldown_active")
  fi
  if [[ "${review_automatic_restart_allowed}" != "false" ]]; then
    review_invariant_blockers+=("automatic_restart_allowed")
  fi
  if [[ "${review_transport_restart_relevant}" != "false" ]]; then
    review_invariant_blockers+=("transport_restart_relevant")
  fi
  if [[ "${review_hash_collection_status}" != "success" ]]; then
    review_invariant_blockers+=("hash_collection_not_success")
  fi
  if [[ "${review_hash_collection_exit_code}" != "0" ]]; then
    review_invariant_blockers+=("hash_collection_exit_code_nonzero")
  fi
  if [[ "${review_immediate_readonly_count}" != "0" ]]; then
    review_invariant_blockers+=("immediate_readonly_actions_pending")
  fi
fi
review_invariant_blocker_count="${#review_invariant_blockers[@]}"
if [[ "${review_invariant_blocker_count}" -eq 0 ]]; then
  review_invariant_blockers_json="[]"
else
  review_invariant_blockers_json="$(printf '%s\n' "${review_invariant_blockers[@]}" | jq -Rsc 'split("\n")[:-1]')"
fi

if [[ "${ready}" != "true" || "${ready_blocker_count}" -ne 0 || "${review_invariant_blocker_count}" -ne 0 ]]; then
  result_json="$(
  jq -n \
    --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --arg local_attempt_out "${LOCAL_ATTEMPT_OUT}" \
    --argjson ready_blocker_count "${ready_blocker_count}" \
    --argjson review_invariant_blocker_count "${review_invariant_blocker_count}" \
    --argjson review_invariant_blockers "${review_invariant_blockers_json}" \
    --argjson review "${review_json}" \
    '{
      source: "scripts/send_nl_no_progress_nudge_guarded.sh",
      generated_at: $generated_at,
      applied: false,
      status: "blocked_by_review_guard",
      reason: (
        if $ready_blocker_count > 0
        then "review guard reported ready blockers"
        elif $review_invariant_blocker_count > 0
        then "review guard send invariants failed"
        else ($review.reason // "review guard did not approve send")
        end
      ),
      local_attempt_out: $local_attempt_out,
      ready_blocker_count: $ready_blocker_count,
      review_invariant_blocker_count: $review_invariant_blocker_count,
      review_invariant_blockers: $review_invariant_blockers,
      review: $review
    }'
  )"
  write_attempt_result "${result_json}"
  exit 0
fi

if [[ "${CONFIRM_NL_NO_PROGRESS_NUDGE}" != "SEND_NL_NO_PROGRESS_NUDGE" ]]; then
  result_json="$(
  jq -n \
    --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --arg local_attempt_out "${LOCAL_ATTEMPT_OUT}" \
    --argjson review "${review_json}" \
    '{
      source: "scripts/send_nl_no_progress_nudge_guarded.sh",
      generated_at: $generated_at,
      applied: false,
      status: "confirmation_required",
      reason: "set CONFIRM_NL_NO_PROGRESS_NUDGE=SEND_NL_NO_PROGRESS_NUDGE after reviewing ready=true output",
      local_attempt_out: $local_attempt_out,
      review: $review
    }'
  )"
  write_attempt_result "${result_json}"
  exit 2
fi

packet_sha="$(jq -r '.expected_hashes.packet // ""' <<<"${review_json}")"
dry_run_sha="$(jq -r '.expected_hashes.dry_run // ""' <<<"${review_json}")"
subscription_payload_sha="$(jq -r '.expected_hashes.subscription_payload // ""' <<<"${review_json}")"
transport_usage_sha="$(jq -r '.expected_hashes.transport_usage // ""' <<<"${review_json}")"
replies_sha="$(jq -r '.expected_hashes.replies // ""' <<<"${review_json}")"
limit="$(jq -r '.no_progress_candidate_count // 0' <<<"${review_json}")"

for sha in \
  "${packet_sha}" \
  "${dry_run_sha}" \
  "${subscription_payload_sha}" \
  "${transport_usage_sha}" \
  "${replies_sha}"; do
  if [[ ! "${sha}" =~ ^[0-9a-f]{64}$ ]]; then
    printf 'invalid expected sha256 from review guard: %s\n' "${sha}" >&2
    exit 3
  fi
done

if [[ ! "${limit}" =~ ^[1-9][0-9]*$ ]]; then
  printf 'invalid no-progress candidate limit from review guard: %s\n' "${limit}" >&2
  exit 3
fi

set +e
send_json="$(
  "${SSH_CMD}" "${SSH_OPTS[@]}" "${NL_HOST}" "
set -euo pipefail
set -a
. /opt/ghost-access-bot/shared/.env
set +a
python3 /opt/ghost-access-bot/current/scripts/send_legacy_no_progress_nudge.py \
  --packet /var/lib/ghost-access/legacy-migration/latest.json \
  --message-send /var/lib/ghost-access/legacy-migration/message-send.json \
  --replies /var/lib/ghost-access/legacy-migration/replies.json \
  --db-path /opt/ghost-access-bot/shared/x0tta6bl4.db \
  --json-out /var/lib/ghost-access/legacy-migration/no-progress-nudge.json \
  --dry-run-report /var/lib/ghost-access/legacy-migration/no-progress-nudge-dry-run.json \
  --subscription-payload-status /var/lib/ghost-access/subscription-payload/latest.json \
  --transport-usage-status /var/lib/ghost-access/transport-usage/latest.json \
  --min-age-minutes 30 \
  --cooldown-hours 12 \
  --dry-run-max-age-minutes 30 \
  --subscription-payload-max-age-minutes 30 \
  --transport-usage-max-age-minutes 15 \
  --replies-max-age-minutes 30 \
  --apply \
  --confirm SEND_LEGACY_NO_PROGRESS_NUDGE \
  --expect-packet-sha256 ${packet_sha} \
  --expect-dry-run-sha256 ${dry_run_sha} \
  --expect-subscription-payload-sha256 ${subscription_payload_sha} \
  --expect-transport-usage-sha256 ${transport_usage_sha} \
  --expect-replies-sha256 ${replies_sha} \
  --limit ${limit} \
  --json
"
)"
send_exit_code=$?
set -e

if [[ "${send_exit_code}" -ne 0 ]]; then
  result_json="$(
  jq -n \
    --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --arg local_attempt_out "${LOCAL_ATTEMPT_OUT}" \
    --argjson review "${review_json}" \
    --argjson send_exit_code "${send_exit_code}" \
    '{
      source: "scripts/send_nl_no_progress_nudge_guarded.sh",
      generated_at: $generated_at,
      applied: false,
      status: "send_failed",
      reason: "remote no-progress nudge sender failed",
      local_attempt_out: $local_attempt_out,
      send_exit_code: $send_exit_code,
      review: $review
    }'
  )"
  write_attempt_result "${result_json}"
  exit "${send_exit_code}"
fi

if ! jq -e 'type == "object"' >/dev/null 2>&1 <<<"${send_json}"; then
  send_output_size_bytes="${#send_json}"
  send_output_sha256="$(printf '%s' "${send_json}" | sha256sum | cut -d ' ' -f1)"
  result_json="$(
  jq -n \
    --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --arg local_attempt_out "${LOCAL_ATTEMPT_OUT}" \
    --arg send_output_sha256 "${send_output_sha256}" \
    --argjson send_output_size_bytes "${send_output_size_bytes}" \
    --argjson review "${review_json}" \
    '{
      source: "scripts/send_nl_no_progress_nudge_guarded.sh",
      generated_at: $generated_at,
      applied: false,
      status: "send_output_invalid",
      reason: "remote no-progress nudge sender returned non-json output",
      local_attempt_out: $local_attempt_out,
      send_output_sha256: $send_output_sha256,
      send_output_size_bytes: $send_output_size_bytes,
      review: $review
    }'
  )"
  write_attempt_result "${result_json}"
  exit 4
fi

mkdir -p "$(dirname "${LOCAL_SEND_OUT}")"
printf '%s\n' "${send_json}" >"${LOCAL_SEND_OUT}"

result_json="$(
jq -n \
  --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg local_send_out "${LOCAL_SEND_OUT}" \
  --arg local_attempt_out "${LOCAL_ATTEMPT_OUT}" \
  --argjson review "${review_json}" \
  --argjson send "${send_json}" \
  '{
    source: "scripts/send_nl_no_progress_nudge_guarded.sh",
    generated_at: $generated_at,
    applied: true,
    status: "sent",
    local_attempt_out: $local_attempt_out,
    local_send_out: $local_send_out,
    review: $review,
    send: $send
  }'
)"
write_attempt_result "${result_json}"
