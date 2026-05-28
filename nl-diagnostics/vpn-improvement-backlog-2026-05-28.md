# VPN Improvement Backlog

generated_at: `2026-05-28T01:00:21.776809+00:00`

## Current Evidence

```text
decision=observe
decision_confidence=high
overall_status=advisory
transport_status=healthy
telegram_media_status=degraded
provider_status=recent_boot_gap
failure_domain=external_network
blocking_history_trend=stable_no_probe_evidence
blocking_history_snapshot_count=5
promoted_source_count=22
nl_write_allowed=false
spb_fallback_allowed=false
```

## Items

### LOCAL-01: Keep one-command read-only evidence collection as the first response

```text
phase=local_now
priority=P0
status=ready
allowed_now=true
nl_write_required=false
mutation_allowed=false
nl_mutation_allowed=false
spb_fallback_allowed=false
```

Reason: Fresh evidence prevents restarting NL for app-only or provider symptoms.

Evidence:
- decision=observe
- transport_status=healthy
- collector=nl-diagnostics/collect_vpn_readonly_snapshot.sh

Next steps:
- run VPN_ENABLE_BLOCKING_PROBES=1 nl-diagnostics/collect_vpn_readonly_snapshot.sh during the next visible outage
- classify the new snapshot before any heal/restart decision
- rebuild nl-diagnostics/current-vpn-decision-2026-05-28.md from the new snapshot

Acceptance:
- snapshot exists under nl-diagnostics/snapshots/
- classification has mutation_allowed=false and nl_mutation_allowed=false
- decision report says observe/local_fix/provider_ticket/operator_review with explicit blocked actions

### LOCAL-02: Keep blocking/app probes as trend evidence, not restart triggers

```text
phase=local_now
priority=P0
status=ready
allowed_now=true
nl_write_required=false
mutation_allowed=false
nl_mutation_allowed=false
spb_fallback_allowed=false
```

Reason: Current app/path probe history does not prove an x-ui outage.

Evidence:
- blocking_history_trend=stable_no_probe_evidence
- blocking_history_snapshot_count=5

Next steps:
- keep nl-diagnostics/blocking_probe_targets.json as the default target set
- add only non-secret public targets when a user reports a new app-specific failure
- do not restart x-ui from direct-vs-SOCKS probe results alone

Acceptance:
- history report includes the latest snapshot
- degraded targets are grouped by service/path
- policy still blocks automatic profile switch and NL mutation

### LOCAL-03: Keep NL source reconciliation local and deploy-blocked

```text
phase=local_now
priority=P1
status=ready
allowed_now=true
nl_write_required=false
mutation_allowed=false
nl_mutation_allowed=false
spb_fallback_allowed=false
```

Reason: Local source must match or explain current NL before any future deploy.

Evidence:
- promoted_source_count=22
- nl_write_allowed=False
- deployable_to_nl=False

Next steps:
- continue using services/nl-server as reviewed local source only
- keep accepted local deltas marked non-deployable until separately reviewed
- run services/nl-server/tools/validate_preflight_readiness.py before any maintenance window

Acceptance:
- manifest JSON is valid
- validate_preflight_readiness reports local_ready_but_deploy_blocked
- source gap summary has no unexplained missing_local_source or local_name_drift

### LOCAL-04: Treat provider boot gaps as watch evidence until transport degrades

```text
phase=local_now
priority=P1
status=watch
allowed_now=true
nl_write_required=false
mutation_allowed=false
nl_mutation_allowed=false
spb_fallback_allowed=false
```

Reason: A boot gap with current healthy transport is a provider-watch signal, not a restart signal.

Evidence:
- provider_status=recent_boot_gap
- failure_domain=external_network

Next steps:
- build a provider packet if transport becomes degraded or critical
- keep boot gap warning in current-vpn-decision report
- avoid local hard heal when provider guard blocks on stale/provider evidence

Acceptance:
- provider packet can be generated from a fresh snapshot
- current decision stays observe while transport is healthy
- provider_ticket is used only when current evidence points to provider/host failure

### NL-FUTURE-01: First approved NL write: stage dry-run health shell split only

```text
phase=future_nl_write
priority=P0
status=blocked_waiting_approval
allowed_now=false
nl_write_required=true
mutation_allowed=false
nl_mutation_allowed=false
spb_fallback_allowed=false
```

Reason: This is the safest first server-side improvement, but NL is read-only now.

Evidence:
- preflight checklist=nl-diagnostics/nl-deploy-preflight-checklist-2026-05-27.md
- target files=health_check_readonly.sh, health_action_policy.py, health_heal_xui.sh

Next steps:
- wait for exact operator approval: approve NL write for health shell split only
- take fresh read-only snapshot and fresh server profile
- create backup, stage files under .staged-<timestamp>, validate, then promote without service restart

Acceptance:
- old health_check.sh remains unchanged
- no systemd reload and no x-ui restart during first write
- post-write read-only verification still reports transport healthy/advisory

### NL-FUTURE-02: Port runtime status semantics to NL only after shell split proves safe

```text
phase=future_nl_write
priority=P1
status=blocked_waiting_approval
allowed_now=false
nl_write_required=true
mutation_allowed=false
nl_mutation_allowed=false
spb_fallback_allowed=false
```

Reason: Local semantic fix is prepared, but changing NL runtime behavior is a later server write.

Evidence:
- local behavior: Telegram media degraded + healthy transport -> advisory/observe
- accepted local delta: services/nl-server/mesh-runtime/vps_build_runtime_state.py

Next steps:
- prepare a separate diff review for vps_build_runtime_state.py
- require fresh snapshot/profile and rollback commands
- deploy only after the read-only health wrappers are already staged and verified

Acceptance:
- NL runtime exposes transport_status separately from telegram_media_status
- Telegram-only degradation no longer makes the whole VPN look critical
- classifier and NL runtime use matching state-contract language

### FUTURE-RESILIENCE-01: Prepare second exit node and manual failover, but keep SPB disabled

```text
phase=future_resilience
priority=P2
status=requirements_documented
allowed_now=true
nl_write_required=false
mutation_allowed=false
nl_mutation_allowed=false
spb_fallback_allowed=false
```

Reason: Provider/host gaps need resilience, but the current SPB path is disabled and not a fallback.

Evidence:
- spb_fallback_allowed=false
- provider_status=recent_boot_gap
- manual_failover_plan=nl-diagnostics/manual-failover-plan-2026-05-28.md
- secondary_probe_template=nl-diagnostics/manual-failover-secondary.example.json
- secondary_config_generator=nl-diagnostics/create_secondary_exit_config.py

Next steps:
- choose a new secondary provider/region that is not SPB
- generate the secondary probe config from public endpoint metadata only
- run probe_secondary_exit.py before any manual profile switch
- define a manual profile switch checklist that requires fresh evidence
- do not reuse disabled SPB as emergency fallback

Acceptance:
- manual failover document exists
- secondary node health check is separate from NL
- automatic switching remains disabled until manual process is tested

No NL or SPB writes were performed by this backlog builder.
