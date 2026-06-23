#!/usr/bin/env bash
set -euo pipefail

# First-party VPN production apply
# Generated locally. Default mode is dry-run; no production command runs
# unless EXECUTE=1, DRY_RUN=0, and APPROVAL has the exact approval phrase.
RUNBOOK_SUMMARY=/mnt/projects/nl-diagnostics/firstparty-production-apply-runbook-20260607T025858Z/summary.json
RUNBOOK_SHA256=ab47f541ddfbaa0b094057dc3736be2e42e591a9be337f1e52f4bb7a6245bf4a
APPROVAL_PHRASE=APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT
DRY_RUN="${DRY_RUN:-1}"
EXECUTE="${EXECUTE:-0}"
APPROVAL="${APPROVAL:-}"
TRANSCRIPT_DIR=/mnt/projects/nl-diagnostics/firstparty-production-operator-transcripts/20260607T034308Z
mkdir -p "$TRANSCRIPT_DIR"
TRANSCRIPT="${TRANSCRIPT:-$TRANSCRIPT_DIR/apply-execution-$(date -u +%Y%m%dT%H%M%SZ).jsonl}"

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

run_step verify_authorization_summary_hash false 'test "$(sha256sum /mnt/projects/nl-diagnostics/firstparty-production-authorization-20260607T010341Z/summary.json | awk '"'"'{print $1}'"'"')" = 33e2ce6aa23bb4cef69928893f170cfa4c526ded92753a0ed3450aff5e77eb23'
run_step verify_apply_packet_hash false 'test "$(sha256sum nl-diagnostics/firstparty-production-apply-packet-20260607T010129Z/summary.json | awk '"'"'{print $1}'"'"')" = aeda9183236859253d6e415169fb7777bac948807fb1a8e9b175651438bda89e'
run_step verify_handoff_summary_hash false 'test "$(sha256sum nl-diagnostics/firstparty-secure-material-handoff-20260607T010254Z/summary.json | awk '"'"'{print $1}'"'"')" = 15950d3120ecfffdd087ded0618d5fa93aa9a1495e7f10ad22d3d3bb796ecf2b'
run_step verify_handoff_archive_hash_and_mode false 'test "$(stat -c '"'"'%a'"'"' /home/x0ttta6bl4/.local/share/x0tta-firstparty-vpn/handoffs/firstparty-production-handoff-20260607T010220Z.tar.gz)" = '"'"'600'"'"' && test "$(sha256sum /home/x0ttta6bl4/.local/share/x0tta-firstparty-vpn/handoffs/firstparty-production-handoff-20260607T010220Z.tar.gz | awk '"'"'{print $1}'"'"')" = c10fb4faea166880483dd3be2790d8ea093f26135ee8fcb5ea1d949cba9cdbc7'
run_step verify_handoff_manifest_hash_and_mode false 'test "$(stat -c '"'"'%a'"'"' /home/x0ttta6bl4/.local/share/x0tta-firstparty-vpn/handoffs/firstparty-production-handoff-20260607T010220Z/MANIFEST.secret-free.json)" = '"'"'600'"'"' && test "$(sha256sum /home/x0ttta6bl4/.local/share/x0tta-firstparty-vpn/handoffs/firstparty-production-handoff-20260607T010220Z/MANIFEST.secret-free.json | awk '"'"'{print $1}'"'"')" = a02ec8feaf77eeb5b3b6976be9df27f4e6324776137c002f530262fc6c799633'
run_step verify_nl_port_still_free_readonly false 'ssh nl '"'"'ss -H -lnt '"'"'"'"'"'"'"'"'( sport = :40467 )'"'"'"'"'"'"'"'"' || true'"'"''
run_step copy_handoff_to_nl_after_approval true 'APPROVAL="${APPROVAL:-}"; test "$APPROVAL" = APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT && ssh nl '"'"'mkdir -p /root/x0tta-firstparty-vpn/production-firstparty-handoff-20260607T010221Z'"'"' && rsync -a --chmod=D700,F600 /home/x0ttta6bl4/.local/share/x0tta-firstparty-vpn/handoffs/firstparty-production-handoff-20260607T010220Z/ nl:/root/x0tta-firstparty-vpn/production-firstparty-handoff-20260607T010221Z/'
run_step install_server_service_after_approval true 'APPROVAL="${APPROVAL:-}"; test "$APPROVAL" = APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT && sudo python3 /root/x0tta-firstparty-vpn/production-firstparty-handoff-20260607T010221Z/x0vpn_node.py install-server-service --config /root/x0tta-firstparty-vpn/production-firstparty-handoff-20260607T010221Z/server.json --service-name x0tta-firstparty-vpn.service --allow-os-mutation --enable-now --uplink-interface eth0'
run_step server_health_post_apply false 'bash -o pipefail -c '"'"'mkdir -p /mnt/projects/nl-diagnostics/firstparty-production-postapply-evidence/20260607T025858Z && ssh nl '"'"'"'"'"'"'"'"'sudo python3 /root/x0tta-firstparty-vpn/production-firstparty-handoff-20260607T010221Z/x0vpn_node.py server-health --config /etc/x0tta-firstparty-vpn-server/server.json --service-name x0tta-firstparty-vpn.service --uplink-interface eth0'"'"'"'"'"'"'"'"' | tee /mnt/projects/nl-diagnostics/firstparty-production-postapply-evidence/20260607T025858Z/server-health.json'"'"''
run_step apply_client_config_after_approval true 'APPROVAL="${APPROVAL:-}"; test "$APPROVAL" = APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT && sudo python3 /root/x0tta-firstparty-vpn/production-firstparty-handoff-20260607T010221Z/x0vpn_node.py install-client-service --config /root/x0tta-firstparty-vpn/production-firstparty-handoff-20260607T010221Z/client.json --service-name x0tta-firstparty-vpn-client.service --allow-os-mutation --enable-now --install-config-sync --require-readiness --require-post-install-health'
run_step client_health_post_apply false 'bash -o pipefail -c '"'"'mkdir -p /mnt/projects/nl-diagnostics/firstparty-production-postapply-evidence/20260607T025858Z && sudo python3 /root/x0tta-firstparty-vpn/production-firstparty-handoff-20260607T010221Z/x0vpn_node.py client-health --config /etc/x0tta-firstparty-vpn-client/client.json --service-name x0tta-firstparty-vpn-client.service | tee /mnt/projects/nl-diagnostics/firstparty-production-postapply-evidence/20260607T025858Z/client-health.json'"'"''
run_step client_doctor_post_apply false 'bash -o pipefail -c '"'"'mkdir -p /mnt/projects/nl-diagnostics/firstparty-production-postapply-evidence/20260607T025858Z && sudo python3 /root/x0tta-firstparty-vpn/production-firstparty-handoff-20260607T010221Z/x0vpn_node.py client-doctor --config /etc/x0tta-firstparty-vpn-client/client.json --service-name x0tta-firstparty-vpn-client.service --require-installed-health | tee /mnt/projects/nl-diagnostics/firstparty-production-postapply-evidence/20260607T025858Z/client-doctor.json'"'"''
run_step build_completion_audit_after_post_apply false 'python3 nl-diagnostics/build_firstparty_production_completion_audit.py --write --json --server-health /mnt/projects/nl-diagnostics/firstparty-production-postapply-evidence/20260607T025858Z/server-health.json --client-health /mnt/projects/nl-diagnostics/firstparty-production-postapply-evidence/20260607T025858Z/client-health.json --client-doctor /mnt/projects/nl-diagnostics/firstparty-production-postapply-evidence/20260607T025858Z/client-doctor.json'

echo "transcript: $TRANSCRIPT"
