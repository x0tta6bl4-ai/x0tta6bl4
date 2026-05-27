# Local Provider Guard Audit, 2026-05-27

## Status

Provider guard is local-only and reads local snapshots only.

```text
NL writes: 0
guard script: scripts/vpn_provider_guard.py
current latest snapshot: nl-diagnostics/snapshots/20260527T072732Z
current guard status: allow
```

Current decision:

```json
{
  "guard_status": "allow",
  "overall_status": "advisory",
  "failure_domain": "external_network",
  "recommended_action": "observe",
  "snapshot_max_age_seconds": 3600,
  "snapshot_stale": false,
  "nl_mutation_allowed": false
}
```

## What It Blocks

Local heal is blocked when the latest local snapshot proves one of these:

```text
overall_status=provider_outage
failure_domain=provider_host
recommended_action=provider_ticket
recommended_action=failover
overall_status=critical and failure_domain=nl_service
```

Reason:

```text
local xray reload/SIGTERM does not fix provider or NL service failure;
it can hide the real incident and create noisy local recovery loops.
```

## What It Allows

The guard allows local healing when no provider/NL block is proven, including:

```text
local_client failures
external_network advisory
Telegram media advisory/degraded with transport still usable
missing/inconclusive local snapshot
```

Missing snapshot is allowed rather than blocked because the guard should not
prevent manual local recovery when it has no evidence.

Exception: forced local healing can require fresh evidence. With
`--require-fresh`, a missing, unreadable, or stale snapshot blocks before any
local mutation.

## Wiring

Local manual heal:

```text
scripts/vpn_heal.sh
  calls scripts/vpn_provider_guard.py --check before ss -K/SIGHUP
  exits before mutation if guard returns block
  VPN_HEAL_FORCE=1 passes --require-fresh by default
  fresh snapshot default max age: 3600 seconds
  manual override: VPN_HEAL_IGNORE_PROVIDER_GUARD=1
```

Freshness controls:

```text
VPN_PROVIDER_GUARD_MAX_AGE_SECONDS=<seconds>
VPN_HEAL_REQUIRE_FRESH_SNAPSHOT=1  require fresh snapshot
VPN_HEAL_REQUIRE_FRESH_SNAPSHOT=0  do not require fresh snapshot even with VPN_HEAL_FORCE=1
```

Local watchdog:

```text
src/network/vpn_watchdog.py
  provider_guard_allows_heal()
  blocks heal() before cooldown and before ss -K/SIGHUP
  SIGTERM local xray is blocked unless VPN_WATCHDOG_ALLOW_HARD_HEAL=1
  hard-heal calls provider guard with --require-fresh before SIGTERM
  disable env: VPN_PROVIDER_GUARD_DISABLE=1
  optional env: VPN_PROVIDER_GUARD_REQUIRE_FRESH=1
  optional env: VPN_PROVIDER_GUARD_MAX_AGE_SECONDS=<seconds>
```

Hard-heal controls:

```text
VPN_WATCHDOG_ALLOW_HARD_HEAL=1  allow SIGTERM local xray after SIGHUP failure
VPN_ALLOW_HARD_HEAL=1           shared fallback flag accepted by watchdog
```

Legacy self-healing daemon:

```text
src/network/self_healing_daemon.py
  provider_guard_allows_heal()
  blocks trigger_healing() before mutation stages
  disable env: VPN_PROVIDER_GUARD_DISABLE=1
  optional env: VPN_PROVIDER_GUARD_REQUIRE_FRESH=1
  optional env: VPN_PROVIDER_GUARD_MAX_AGE_SECONDS=<seconds>
```

## Commands

```bash
python3 scripts/vpn_provider_guard.py --json
python3 scripts/vpn_provider_guard.py --check
python3 scripts/vpn_provider_guard.py --check --require-fresh --max-age-seconds 3600
```

Exit codes:

```text
0  allow
10 block
```

## Validation

```text
python3 -m pytest tests/unit/scripts/test_vpn_provider_guard_unit.py tests/unit/scripts/test_vpn_heal_provider_guard_unit.py tests/unit/scripts/test_vpn_status_json_unit.py tests/unit/network/test_vpn_health_autodetect_unit.py -q --no-cov
36 passed
```

Syntax checks:

```text
bash -n scripts/vpn_heal.sh scripts/vpn_status.sh
python3 -m py_compile scripts/vpn_provider_guard.py src/network/vpn_watchdog.py src/network/self_healing_daemon.py
```
