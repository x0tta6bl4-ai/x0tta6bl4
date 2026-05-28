# Manual Failover Plan

generated_at: `2026-05-28T01:17:07.746302+00:00`

## Status

```text
status=planning_not_active
current_decision=observe
decision_confidence=high
overall_status=advisory
transport_status=advisory
failure_domain=external_network
provider_status=recent_boot_gap
spb_fallback_allowed=false
automatic_failover_allowed=false
nl_write_allowed=false
```

## Candidate Requirements

### NODE-01

Requirement: Use a new secondary exit node, not SPB

Acceptance: provider/region/account are documented and spb_fallback_allowed=false remains true in policy

### NODE-02

Requirement: Use a different provider and region from NL

Acceptance: provider outage on NL should not imply outage on the secondary node

### NODE-03

Requirement: Keep secrets out of repo and reports

Acceptance: only redacted profile shape or checksums are stored locally; no raw URI/private key/token

### NODE-04

Requirement: Expose an independent health check

Acceptance: probe_secondary_exit.py can verify TCP reachability and expected exit IP without touching NL

### NODE-05

Requirement: Use a minimal daily/emergency profile split

Acceptance: daily NL profile and emergency secondary profile are distinct; automatic switching remains disabled

## Activation Gates

### GATE-01

Gate: fresh read-only NL snapshot with blocking probes

Pass condition: snapshot is current and classifier says provider_ticket/failover or NL transport is critical while local client is healthy

### GATE-02

Gate: local client is not the failure domain

Pass condition: vpn_status shows local route/SOCKS/client are OK; otherwise fix local client first

### GATE-03

Gate: secondary node health is independently verified

Pass condition: probe_secondary_exit.py reports healthy, or endpoint_reachable_profile_unverified before the profile switch test

### GATE-04

Gate: explicit manual approval

Pass condition: operator approves a manual client/profile switch; automatic failover remains false

### GATE-05

Gate: SPB remains excluded

Pass condition: selected emergency profile is not SPB and does not run sync_spb_standalone_clients.py

## Procedures

### prepare_now

- choose a new provider/region for a future secondary node
- create safe probe config with nl-diagnostics/create_secondary_exit_config.py using public endpoint metadata only
- prepare local-only health probe config from nl-diagnostics/manual-failover-secondary.example.json as a fallback template
- document manual switch and rollback steps without storing secrets

### during_incident

- collect VPN_ENABLE_BLOCKING_PROBES=1 read-only snapshot
- build current VPN decision report and provider packet if needed
- run python3 nl-diagnostics/probe_secondary_exit.py --config <redacted-secondary-config>
- perform client-side manual switch only after explicit approval
- record timeline and keep NL unchanged while diagnosing provider/NL state

### rollback

- collect a fresh NL read-only snapshot showing transport healthy/advisory
- switch the client back manually to NL daily profile
- verify exit IP, route bypass, packet loss, and watchdog metrics
- leave secondary profile available but inactive

## Local Secondary Probe

```text
script=nl-diagnostics/probe_secondary_exit.py
config_generator=nl-diagnostics/create_secondary_exit_config.py
example_config=nl-diagnostics/manual-failover-secondary.example.json
placeholder_status=planning_template
mutation_allowed=false
nl_mutation_allowed=false
spb_fallback_allowed=false
```

## Blocked Actions

- do not use SPB as fallback while SPB is disabled
- do not run sync_spb_standalone_clients.py as recovery
- do not auto-switch profiles
- do not change NL during failover unless a separate NL write approval exists
- do not store raw VPN URIs, UUIDs, private keys, or bot tokens in reports

No NL or SPB writes were performed by this plan builder.
