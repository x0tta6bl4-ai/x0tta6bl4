#!/usr/bin/env bash
set -euo pipefail

# First-party VPN production rollback
# Generated locally. Default mode is dry-run; no production command runs
# unless EXECUTE=1, DRY_RUN=0, and APPROVAL has the exact approval phrase.
RUNBOOK_SUMMARY=/mnt/projects/nl-diagnostics/firstparty-production-apply-runbook-20260607T025858Z/summary.json
RUNBOOK_SHA256=ab47f541ddfbaa0b094057dc3736be2e42e591a9be337f1e52f4bb7a6245bf4a
APPROVAL_PHRASE=APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT
DRY_RUN="${DRY_RUN:-1}"
EXECUTE="${EXECUTE:-0}"
APPROVAL="${APPROVAL:-}"
TRANSCRIPT_DIR=/mnt/projects/nl-diagnostics/firstparty-production-operator-transcripts/20260607T031432Z
mkdir -p "$TRANSCRIPT_DIR"
TRANSCRIPT="${TRANSCRIPT:-$TRANSCRIPT_DIR/transcript-$(date -u +%Y%m%dT%H%M%SZ).jsonl}"

current_sha="$(sha256sum "$RUNBOOK_SUMMARY" | awk '{print $1}')"
if [[ "$current_sha" != "$RUNBOOK_SHA256" ]]; then
  echo "runbook hash mismatch: $current_sha != $RUNBOOK_SHA256" >&2
  exit 40
fi

if [[ "$EXECUTE" == "1" || "$DRY_RUN" == "0" ]]; then
  if [[ "$EXECUTE" != "1" || "$DRY_RUN" != "0" ]]; then
    echo "execution requires both EXECUTE=1 and DRY_RUN=0" >&2
    exit 41
  fi
  if [[ "$APPROVAL" != "$APPROVAL_PHRASE" ]]; then
    echo "execution requires APPROVAL=$APPROVAL_PHRASE" >&2
    exit 42
  fi
else
  echo "dry-run only: set EXECUTE=1 DRY_RUN=0 and APPROVAL=$APPROVAL_PHRASE to run"
fi

log_event() {
  local event="$1"
  local step_id="$2"
  local rc="${3:-0}"
  printf '{"ts":"%s","event":"%s","step_id":"%s","rc":%s}\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$event" "$step_id" "$rc" >> "$TRANSCRIPT"
}

run_step() {
  local step_id="$1"
  local mutation="$2"
  local command="$3"
  echo "==> $step_id"
  log_event "start" "$step_id" 0
  if [[ "$EXECUTE" != "1" || "$DRY_RUN" != "0" ]]; then
    printf '[dry-run] %s\n' "$command"
    log_event "dry_run" "$step_id" 0
    return 0
  fi
  if [[ "$mutation" == "true" && "$APPROVAL" != "$APPROVAL_PHRASE" ]]; then
    echo "mutating step blocked without approval: $step_id" >&2
    exit 43
  fi
  set +e
  export APPROVAL
  bash -o pipefail -c "$command"
  local rc=$?
  set -e
  log_event "finish" "$step_id" "$rc"
  if [[ "$rc" -ne 0 ]]; then
    echo "step failed: $step_id rc=$rc" >&2
    exit "$rc"
  fi
}

run_step rollback_client_policy_and_service_after_approval true 'APPROVAL="${APPROVAL:-}"; test "$APPROVAL" = APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT && sudo python3 /root/x0tta-firstparty-vpn/production-firstparty-handoff-20260607T010221Z/x0vpn_node.py client-policy-rollback --config /etc/x0tta-firstparty-vpn-client/client.json --allow-os-mutation --enable-kill-switch && sudo python3 /root/x0tta-firstparty-vpn/production-firstparty-handoff-20260607T010221Z/x0vpn_node.py uninstall-client-service --service-name x0tta-firstparty-vpn-client.service --allow-os-mutation'
run_step rollback_server_service_after_approval true 'APPROVAL="${APPROVAL:-}"; test "$APPROVAL" = APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT && sudo python3 /root/x0tta-firstparty-vpn/production-firstparty-handoff-20260607T010221Z/x0vpn_node.py uninstall-server-service --service-name x0tta-firstparty-vpn.service --allow-os-mutation'

echo "transcript: $TRANSCRIPT"
