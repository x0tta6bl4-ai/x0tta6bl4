#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
NL_HOST="${NL_HOST:-nl}"

SSH_OPTS=(
  -o BatchMode=yes
  -o ConnectTimeout=10
)

REMOTE_SERVICES=(
  ghost-access-transport-usage-evidence.service
  ghost-access-live-subscription-payload-check.service
  ghost-access-legacy-migration-reply-collector.service
  ghost-access-legacy-migration-progress.service
  ghost-access-legacy-no-progress-nudge-dry-run.service
)

REMOTE_FILES=(
  "/var/lib/ghost-access/transport-usage/latest.json:${PROJECT_ROOT}/nl-diagnostics/nl-transport-usage-latest.json"
  "/var/lib/ghost-access/subscription-payload/latest.json:${PROJECT_ROOT}/nl-diagnostics/nl-live-subscription-payload-latest.json"
  "/var/lib/ghost-access/legacy-migration/no-progress-nudge-dry-run.json:${PROJECT_ROOT}/nl-diagnostics/nl-legacy-no-progress-nudge-dry-run-latest.json"
  "/var/lib/ghost-access/legacy-migration/progress.json:${PROJECT_ROOT}/nl-diagnostics/nl-legacy-client-migration-progress-2026-06-05.json"
  "/var/lib/ghost-access/legacy-migration/replies.json:${PROJECT_ROOT}/nl-diagnostics/nl-legacy-client-migration-replies-2026-06-05.json"
)

printf 'Refreshing NL read-only VPN evidence from %s\n' "${NL_HOST}"
printf 'Project root: %s\n' "${PROJECT_ROOT}"

printf '\n[x-ui before]\n'
ssh "${SSH_OPTS[@]}" "${NL_HOST}" \
  'systemctl show x-ui.service --property=ActiveState,SubState,MainPID,NRestarts,ExecMainStatus --no-pager'

printf '\n[start read-only collectors]\n'
remote_start_cmd="set -euo pipefail"
for service in "${REMOTE_SERVICES[@]}"; do
  remote_start_cmd+="; sudo systemctl start ${service}"
done
remote_start_cmd+="; systemctl show ${REMOTE_SERVICES[*]} -p Id -p Result -p ExecMainStatus --no-pager"
ssh "${SSH_OPTS[@]}" "${NL_HOST}" "${remote_start_cmd}"

printf '\n[pull evidence]\n'
mkdir -p "${PROJECT_ROOT}/nl-diagnostics"
for mapping in "${REMOTE_FILES[@]}"; do
  remote_path="${mapping%%:*}"
  local_path="${mapping#*:}"
  printf '%s -> %s\n' "${remote_path}" "${local_path}"
  scp "${SSH_OPTS[@]}" "${NL_HOST}:${remote_path}" "${local_path}"
done

printf '\n[x-ui after]\n'
ssh "${SSH_OPTS[@]}" "${NL_HOST}" \
  'systemctl show x-ui.service --property=ActiveState,SubState,MainPID,NRestarts,ExecMainStatus --no-pager'

printf '\n[compact status]\n'
if command -v jq >/dev/null 2>&1; then
  bash "${PROJECT_ROOT}/scripts/vpn_status.sh" --json | jq '{
    overall_status,
    anti_dpi_readiness: {
      distribution_ready: .anti_dpi_readiness.distribution_ready,
      status: .anti_dpi_readiness.status,
      warnings: .anti_dpi_readiness.warnings
    },
    user_connectivity: {
      status: .user_connectivity.status,
      target_active_user_count: .user_connectivity.target_active_user_count,
      positive_signal_count: .user_connectivity.positive_signal_count,
      no_progress_candidate_count: .user_connectivity.no_progress_candidate_count,
      proven: .user_connectivity.user_connectivity_proven,
      blockers: .user_connectivity.blockers
    },
    transport_usage: {
      status: .transport_usage.status,
      severity: .transport_usage.summary.severity,
      restart_relevant: .transport_usage.summary.restart_relevant,
      seconds_until_stale: .transport_usage.seconds_until_stale
    },
    next_safe_action: {
      action: .next_safe_action.action,
      earliest_mutation_at: .next_safe_action.earliest_mutation_at,
      immediate_readonly_actions: .next_safe_action.immediate_readonly_actions,
      deferred_readonly_actions: .next_safe_action.deferred_readonly_actions,
      user_message_allowed_after_review: .next_safe_action.user_message_allowed_after_review
    }
  }'
else
  bash "${PROJECT_ROOT}/scripts/vpn_status.sh" --json
fi
