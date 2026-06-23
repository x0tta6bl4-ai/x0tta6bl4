# First-Party VPN Production Apply Runbook

generated_at: `2026-06-07T02:58:58Z`
ok: `true`
endpoint: `tcp://89.125.1.107:40467`
approval_phrase_required: `APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT`
production_mutation_allowed: `false`

## Checks

| Check | Passed |
|---|---|
| `apply_packet_hash_bound_to_authorization` | `true` |
| `apply_packet_ok` | `true` |
| `approval_not_present` | `true` |
| `authorization_approval_guarded` | `true` |
| `authorization_evidence_fresh` | `true` |
| `authorization_no_mutation` | `true` |
| `authorization_ok` | `true` |
| `client_rollback_scope_firstparty_only` | `true` |
| `completion_audit_command_present` | `true` |
| `endpoint_external_shape` | `true` |
| `guarded_apply_commands_present` | `true` |
| `guarded_copy_command_present` | `true` |
| `handoff_archive_exists` | `true` |
| `handoff_archive_hash_bound_to_authorization` | `true` |
| `handoff_archive_private` | `true` |
| `handoff_manifest_exists` | `true` |
| `handoff_manifest_hash_bound_to_authorization` | `true` |
| `handoff_manifest_private` | `true` |
| `handoff_manifest_secret_free` | `true` |
| `handoff_summary_hash_bound_to_authorization` | `true` |
| `handoff_summary_ok` | `true` |
| `mutating_commands_have_approval_guard` | `true` |
| `mutating_x0vpn_commands_have_allow_os_mutation` | `true` |
| `no_legacy_service_targets_in_commands` | `true` |
| `no_nl_or_spb_writes_performed` | `true` |
| `os_mutation_not_performed` | `true` |
| `post_apply_evidence_paths_present` | `true` |
| `post_apply_validation_commands_capture_json` | `true` |
| `post_apply_validation_commands_present` | `true` |
| `precheck_commands_present` | `true` |
| `production_mutation_blocked` | `true` |
| `rollback_commands_present` | `true` |
| `runbook_does_not_execute_commands` | `true` |
| `server_rollback_scope_firstparty_only` | `true` |
| `service_names_firstparty_only` | `true` |

## Failed Checks

- none

## Operator Commands

### verify_authorization_summary_hash

- phase: `local-precheck`
- run_on: `operator-workstation`
- mutation: `false`
- approval_required: `false`

```bash
test "$(sha256sum /mnt/projects/nl-diagnostics/firstparty-production-authorization-20260607T010341Z/summary.json | awk '{print $1}')" = 33e2ce6aa23bb4cef69928893f170cfa4c526ded92753a0ed3450aff5e77eb23
```

### verify_apply_packet_hash

- phase: `local-precheck`
- run_on: `operator-workstation`
- mutation: `false`
- approval_required: `false`

```bash
test "$(sha256sum nl-diagnostics/firstparty-production-apply-packet-20260607T010129Z/summary.json | awk '{print $1}')" = aeda9183236859253d6e415169fb7777bac948807fb1a8e9b175651438bda89e
```

### verify_handoff_summary_hash

- phase: `local-precheck`
- run_on: `operator-workstation`
- mutation: `false`
- approval_required: `false`

```bash
test "$(sha256sum nl-diagnostics/firstparty-secure-material-handoff-20260607T010254Z/summary.json | awk '{print $1}')" = 15950d3120ecfffdd087ded0618d5fa93aa9a1495e7f10ad22d3d3bb796ecf2b
```

### verify_handoff_archive_hash_and_mode

- phase: `local-precheck`
- run_on: `operator-workstation`
- mutation: `false`
- approval_required: `false`

```bash
test "$(stat -c '%a' /home/x0ttta6bl4/.local/share/x0tta-firstparty-vpn/handoffs/firstparty-production-handoff-20260607T010220Z.tar.gz)" = '600' && test "$(sha256sum /home/x0ttta6bl4/.local/share/x0tta-firstparty-vpn/handoffs/firstparty-production-handoff-20260607T010220Z.tar.gz | awk '{print $1}')" = c10fb4faea166880483dd3be2790d8ea093f26135ee8fcb5ea1d949cba9cdbc7
```

### verify_handoff_manifest_hash_and_mode

- phase: `local-precheck`
- run_on: `operator-workstation`
- mutation: `false`
- approval_required: `false`

```bash
test "$(stat -c '%a' /home/x0ttta6bl4/.local/share/x0tta-firstparty-vpn/handoffs/firstparty-production-handoff-20260607T010220Z/MANIFEST.secret-free.json)" = '600' && test "$(sha256sum /home/x0ttta6bl4/.local/share/x0tta-firstparty-vpn/handoffs/firstparty-production-handoff-20260607T010220Z/MANIFEST.secret-free.json | awk '{print $1}')" = a02ec8feaf77eeb5b3b6976be9df27f4e6324776137c002f530262fc6c799633
```

### verify_nl_port_still_free_readonly

- phase: `remote-readonly-precheck`
- run_on: `nl`
- mutation: `false`
- approval_required: `false`

```bash
ssh nl 'ss -H -lnt '"'"'( sport = :40467 )'"'"' || true'
```

### copy_handoff_to_nl_after_approval

- phase: `guarded-copy`
- run_on: `operator-workstation`
- mutation: `true`
- approval_required: `true`

```bash
APPROVAL="${APPROVAL:-}"; test "$APPROVAL" = APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT && ssh nl 'mkdir -p /root/x0tta-firstparty-vpn/production-firstparty-handoff-20260607T010221Z' && rsync -a --chmod=D700,F600 /home/x0ttta6bl4/.local/share/x0tta-firstparty-vpn/handoffs/firstparty-production-handoff-20260607T010220Z/ nl:/root/x0tta-firstparty-vpn/production-firstparty-handoff-20260607T010221Z/
```

### install_server_service_after_approval

- phase: `server-apply`
- run_on: `nl`
- mutation: `true`
- approval_required: `true`

```bash
APPROVAL="${APPROVAL:-}"; test "$APPROVAL" = APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT && sudo python3 /root/x0tta-firstparty-vpn/production-firstparty-handoff-20260607T010221Z/x0vpn_node.py install-server-service --config /root/x0tta-firstparty-vpn/production-firstparty-handoff-20260607T010221Z/server.json --service-name x0tta-firstparty-vpn.service --allow-os-mutation --enable-now --uplink-interface eth0
```

### server_health_post_apply

- phase: `post-apply-validation`
- run_on: `operator-workstation`
- mutation: `false`
- approval_required: `false`

```bash
bash -o pipefail -c 'mkdir -p /mnt/projects/nl-diagnostics/firstparty-production-postapply-evidence/20260607T025858Z && ssh nl '"'"'sudo python3 /root/x0tta-firstparty-vpn/production-firstparty-handoff-20260607T010221Z/x0vpn_node.py server-health --config /etc/x0tta-firstparty-vpn-server/server.json --service-name x0tta-firstparty-vpn.service --uplink-interface eth0'"'"' | tee /mnt/projects/nl-diagnostics/firstparty-production-postapply-evidence/20260607T025858Z/server-health.json'
```

### apply_client_config_after_approval

- phase: `client-apply`
- run_on: `client-host`
- mutation: `true`
- approval_required: `true`

```bash
APPROVAL="${APPROVAL:-}"; test "$APPROVAL" = APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT && sudo python3 /root/x0tta-firstparty-vpn/production-firstparty-handoff-20260607T010221Z/x0vpn_node.py install-client-service --config /root/x0tta-firstparty-vpn/production-firstparty-handoff-20260607T010221Z/client.json --service-name x0tta-firstparty-vpn-client.service --allow-os-mutation --enable-now --install-config-sync --require-readiness --require-post-install-health
```

### client_health_post_apply

- phase: `post-apply-validation`
- run_on: `client-host`
- mutation: `false`
- approval_required: `false`

```bash
bash -o pipefail -c 'mkdir -p /mnt/projects/nl-diagnostics/firstparty-production-postapply-evidence/20260607T025858Z && sudo python3 /root/x0tta-firstparty-vpn/production-firstparty-handoff-20260607T010221Z/x0vpn_node.py client-health --config /etc/x0tta-firstparty-vpn-client/client.json --service-name x0tta-firstparty-vpn-client.service | tee /mnt/projects/nl-diagnostics/firstparty-production-postapply-evidence/20260607T025858Z/client-health.json'
```

### client_doctor_post_apply

- phase: `post-apply-validation`
- run_on: `client-host`
- mutation: `false`
- approval_required: `false`

```bash
bash -o pipefail -c 'mkdir -p /mnt/projects/nl-diagnostics/firstparty-production-postapply-evidence/20260607T025858Z && sudo python3 /root/x0tta-firstparty-vpn/production-firstparty-handoff-20260607T010221Z/x0vpn_node.py client-doctor --config /etc/x0tta-firstparty-vpn-client/client.json --service-name x0tta-firstparty-vpn-client.service --require-installed-health | tee /mnt/projects/nl-diagnostics/firstparty-production-postapply-evidence/20260607T025858Z/client-doctor.json'
```

### build_completion_audit_after_post_apply

- phase: `post-apply-validation`
- run_on: `operator-workstation`
- mutation: `false`
- approval_required: `false`

```bash
python3 nl-diagnostics/build_firstparty_production_completion_audit.py --write --json --server-health /mnt/projects/nl-diagnostics/firstparty-production-postapply-evidence/20260607T025858Z/server-health.json --client-health /mnt/projects/nl-diagnostics/firstparty-production-postapply-evidence/20260607T025858Z/client-health.json --client-doctor /mnt/projects/nl-diagnostics/firstparty-production-postapply-evidence/20260607T025858Z/client-doctor.json
```

### rollback_client_policy_and_service_after_approval

- phase: `rollback`
- run_on: `client-host`
- mutation: `true`
- approval_required: `true`

```bash
APPROVAL="${APPROVAL:-}"; test "$APPROVAL" = APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT && sudo python3 /root/x0tta-firstparty-vpn/production-firstparty-handoff-20260607T010221Z/x0vpn_node.py client-policy-rollback --config /etc/x0tta-firstparty-vpn-client/client.json --allow-os-mutation --enable-kill-switch && sudo python3 /root/x0tta-firstparty-vpn/production-firstparty-handoff-20260607T010221Z/x0vpn_node.py uninstall-client-service --service-name x0tta-firstparty-vpn-client.service --allow-os-mutation
```

### rollback_server_service_after_approval

- phase: `rollback`
- run_on: `nl`
- mutation: `true`
- approval_required: `true`

```bash
APPROVAL="${APPROVAL:-}"; test "$APPROVAL" = APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT && sudo python3 /root/x0tta-firstparty-vpn/production-firstparty-handoff-20260607T010221Z/x0vpn_node.py uninstall-server-service --service-name x0tta-firstparty-vpn.service --allow-os-mutation
```

## Evidence

- apply_packet_summary_path: `nl-diagnostics/firstparty-production-apply-packet-20260607T010129Z/summary.json`
- authorization_summary_path: `/mnt/projects/nl-diagnostics/firstparty-production-authorization-20260607T010341Z/summary.json`
- handoff_archive: `/home/x0ttta6bl4/.local/share/x0tta-firstparty-vpn/handoffs/firstparty-production-handoff-20260607T010220Z.tar.gz`
- handoff_dir: `/home/x0ttta6bl4/.local/share/x0tta-firstparty-vpn/handoffs/firstparty-production-handoff-20260607T010220Z`
- handoff_manifest: `/home/x0ttta6bl4/.local/share/x0tta-firstparty-vpn/handoffs/firstparty-production-handoff-20260607T010220Z/MANIFEST.secret-free.json`
- handoff_summary_path: `nl-diagnostics/firstparty-secure-material-handoff-20260607T010254Z/summary.json`

## Post-Apply Evidence Files

- client_doctor_local_path: `/mnt/projects/nl-diagnostics/firstparty-production-postapply-evidence/20260607T025858Z/client-doctor.json`
- client_health_local_path: `/mnt/projects/nl-diagnostics/firstparty-production-postapply-evidence/20260607T025858Z/client-health.json`
- evidence_dir: `/mnt/projects/nl-diagnostics/firstparty-production-postapply-evidence/20260607T025858Z`
- server_health_local_path: `/mnt/projects/nl-diagnostics/firstparty-production-postapply-evidence/20260607T025858Z/server-health.json`

This runbook was generated locally and did not execute any command.
Do not run mutating commands unless the explicit approval phrase is present in the current conversation.
