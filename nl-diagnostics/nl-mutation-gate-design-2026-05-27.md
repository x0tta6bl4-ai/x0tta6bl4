# NL Mutation Gate Design, 2026-05-27

## Status

This is local-only design and source preparation.

```text
NL write permission: false
deployable_to_nl: false
```

No NL service was restarted.

## Problem

The real NL `health_check.sh` can restart `x-ui`:

```text
systemctl restart x-ui
```

The pulled source uses:

```text
RESTART_COOLDOWN_SEC=600
```

That is too aggressive for provider or hypervisor incidents. A provider-side
shutdown, high CPU steal, or disk wait spike should not trigger restart loops.

## Local Policy Source

Prepared:

```text
services/nl-server/mesh-runtime/health_action_policy.py
services/nl-server/mesh-runtime/health_check_readonly.sh
services/nl-server/mesh-runtime/health_heal_xui.sh
services/nl-server/tests/test_health_action_policy.py
```

The policy is pure code. It does not call `systemctl`, does not write files, and
does not connect to NL.

## Restart Gates

Future `x-ui` restart is allowed only when all gates pass:

```text
recommended_action == restart_primary
listener_443_ok is false OR xui_service_ok is false
provider guard is not active
explicit mutation flag is true
restart cooldown is expired
```

Default cooldown:

```text
1800 seconds
```

Blocked provider statuses:

```text
provider_outage
overloaded
host_degraded
```

## Tested Decisions

```text
observe action -> no restart
missing mutation flag -> blocked_mutation_flag
provider outage -> blocked_provider_guard
cooldown active -> blocked_cooldown
all gates pass -> restart_xui
healthy primary -> no restart
```

Validation:

```text
python3 services/nl-server/tests/test_health_action_policy.py
Ran 6 tests: OK
bash -n services/nl-server/mesh-runtime/health_check_readonly.sh services/nl-server/mesh-runtime/health_heal_xui.sh
OK
health_check_readonly.sh fixture run
OK
health_heal_xui.sh without approval
blocked_mutation_flag
health_heal_xui.sh with approval but without execute flag
dry-run restart_xui
python3 services/nl-server/tools/validate_preflight_readiness.py
ok=true, deploy_status=local_ready_but_deploy_blocked
```

## Future Shell Split

The future deployed shape should be:

```text
health_check_readonly.sh
  reads runtime-state
  prints state
  never restarts services

health_heal_xui.sh
  calls health_action_policy.py
  requires explicit mutation flag
  writes cooldown state only after successful restart
  logs pre/post snapshot ids
```

## Required Before NL Deploy

```text
fresh read-only snapshot
fresh nl-server-profile
hash diff against current NL health_check.sh
x-ui db backup command
x-ui generated config backup command
rollback command
explicit operator approval
maintenance window
```

Detailed preflight:

```text
nl-diagnostics/nl-deploy-preflight-checklist-2026-05-27.md
```
