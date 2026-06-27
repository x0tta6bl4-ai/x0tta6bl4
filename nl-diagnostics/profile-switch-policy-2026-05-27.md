# Profile Switch Policy, 2026-05-27

## Status

This policy covers NL runtime signals like:

```text
runtime_mode=anti_block
runtime_recommended_action=switch_profile
```

It is local policy only. It does not switch profiles, write to NL, restart
services, edit x-ui, or deploy code.

## Current Rule

`switch_profile` is advisory unless stronger evidence exists.

If core transport is healthy/advisory, x-ui/listeners are healthy, local VPN is
OK, and packet loss is zero, the decision is:

```text
decision=manual_profile_review
automatic_allowed=false
manual_allowed=false
manual_review_required=true
nl_mutation_allowed=false
```

Meaning: do not restart NL and do not auto-switch. Review manually with fresh
evidence.

## Gates

Profile switch review requires:

```text
fresh read-only snapshot
no active provider outage
no local client critical failure
transport_status=healthy|advisory
explicit manual approval before any actual profile change
```

Blocked cases:

```text
stale snapshot -> blocked_stale_snapshot
provider outage -> blocked_provider_guard
local client critical -> blocked_local_client
transport degraded/unknown -> operator_review
```

## Commands

Classify current snapshot:

```bash
python3 nl-diagnostics/classify_vpn_snapshot.py nl-diagnostics/snapshots/<timestamp>
```

Run policy tests:

```bash
python3 nl-diagnostics/test_profile_switch_policy.py
```

## Example Interpretation

For fresh snapshot `20260527T083246Z`, NL reported:

```text
mode=anti_block
recommended_action=switch_profile
transport_health_status=healthy
listener_443_ok=true
xui_service_ok=true
packet_loss_percent=0
```

That is not an x-ui outage. It is a manual review signal.

Latest fresh snapshot `20260527T150900Z` no longer reports
`recommended_action=switch_profile`; it reports `recommended_action=observe`.
The policy decision is therefore:

```text
decision=observe
automatic_allowed=false
nl_mutation_allowed=false
```
