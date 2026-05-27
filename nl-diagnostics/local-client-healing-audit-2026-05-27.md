# Local Client Healing Audit, 2026-05-27

## Status

This audit covers local client-side VPN code only.

```text
NL writes: 0
files reviewed:
  scripts/vpn_status.sh
  scripts/vpn_heal.sh
  scripts/vpn_provider_guard.py
  src/network/vpn_watchdog.py
  src/network/self_healing_daemon.py
  tests/unit/network/test_vpn_health_autodetect_unit.py
  tests/unit/scripts/test_vpn_status_json_unit.py
  tests/unit/scripts/test_vpn_provider_guard_unit.py
  tests/unit/scripts/test_vpn_heal_provider_guard_unit.py
```

## Current Behavior

`vpn_status.sh` is a local health dashboard:

```text
default VPN_SERVER: 89.125.1.107
default VPN_PORT: 39829
checks xray process
checks x0tta-node.service
checks singbox_tun
checks route loop risk
checks SOCKS5 handshake and external IP
checks packet loss
checks watchdog metrics
checks boot validation result
supports --json state-contract output
```

`vpn_heal.sh` is manual emergency local healing:

```text
does nothing if proxy is healthy and stale TCP states are zero
requires VPN_HEAL_FORCE=1 to reload when no heal is needed
checks provider guard before ss -K or SIGHUP
requires a fresh snapshot by default when VPN_HEAL_FORCE=1
can run ss -K for FIN-WAIT-2/CLOSE-WAIT
can send SIGHUP to local xray
does not touch NL
```

`vpn_watchdog.py`:

```text
ENABLE_HEAL default: false
ENABLE_HARD_HEAL default: false
monitors stale TCP states, SOCKS5, packet loss
exports metrics on 127.0.0.1:9091
can run ss -K and SIGHUP xray only if healing is explicitly enabled
can send SIGTERM to local xray only if VPN_WATCHDOG_ALLOW_HARD_HEAL=1
requires fresh provider-guard evidence before SIGTERM
```

`self_healing_daemon.py`:

```text
ENABLE_HEAL default: false
can run ss -K and SIGHUP xray when enabled
Reality key rotation remains separately gated by VPN_ENABLE_REALITY_ROTATION
```

## Local Fix Applied

The local client heal cooldown now matches the safer policy:

```text
src/network/vpn_watchdog.py
  HEAL_COOLDOWN_SEC default: 1800
  env override: VPN_HEAL_COOLDOWN_SEC
  default VPN_PORT: 39829

src/network/self_healing_daemon.py
  _HEAL_COOLDOWN default: 1800
  env override: VPN_HEAL_COOLDOWN_SEC or VPN_SELF_HEAL_COOLDOWN_SEC

scripts/vpn_status.sh
  --json emits overall_status, failure_domain, recommended_action, mutation gates, and evidence
  route loop maps to critical/local_client/local_soft_heal

scripts/vpn_provider_guard.py
  reads latest local snapshot only
  blocks local healing on provider_outage/provider_host/provider_ticket/failover
  blocks local healing on critical nl_service
  warns on stale snapshots by default
  blocks stale/missing/unknown snapshots when --require-fresh is used
  default freshness limit: 3600 sec
  current latest snapshot decision: allow

src/network/vpn_watchdog.py
  SIGTERM local xray is blocked by default
  explicit hard-heal flag: VPN_WATCHDOG_ALLOW_HARD_HEAL=1
  hard-heal always calls provider guard with --require-fresh

src/network/self_healing_daemon.py
  VPN_PROVIDER_GUARD_REQUIRE_FRESH=1 now fails closed if the guard is missing or inconclusive
```

Why:

```text
60 seconds was too aggressive if local healing is enabled.
30 minutes reduces restart/kill loops during provider or external-network instability.
39829 matches the current local client profile shown by vpn_status.sh.
JSON output lets local checks use the same state-contract fields as the NL snapshot classifier.
Freshness checks stop forced local reloads from using old NL/provider evidence.
Hard-heal gating prevents a normal watchdog reload path from escalating to local xray kill.
```

## Remaining Risks

These are intentionally not changed yet:

```text
self_healing_daemon.py can still run deeper stages if explicit env flags are enabled.
provider guard intentionally allows inconclusive/missing snapshots unless fresh evidence is required.
```

## Recommended Next Local Changes

1. Split local healing actions:

```text
local_soft_heal: route refresh and stale TCP cleanup
local_reload: SIGHUP local xray only
local_hard_heal: SIGTERM local xray, explicit flag only
```

2. Extend hard-heal guard:

```text
decide whether to add a separate manual CLI for local_hard_heal;
keep SIGTERM outside normal watchdog recovery unless VPN_WATCHDOG_ALLOW_HARD_HEAL=1.
```

3. Keep NL healing forbidden unless `nl_write_allowed=true` appears in a future
approved manifest.

## Validation

```text
python3 -m py_compile src/network/vpn_watchdog.py src/network/self_healing_daemon.py
python3 -m pytest tests/unit/scripts/test_vpn_provider_guard_unit.py tests/unit/scripts/test_vpn_heal_provider_guard_unit.py tests/unit/scripts/test_vpn_status_json_unit.py tests/unit/network/test_vpn_health_autodetect_unit.py -q --no-cov
bash scripts/vpn_status.sh --json | python3 -m json.tool
36 passed
```

Note:

```text
The same pytest file also passed with the repository coverage plugin, but that
run returned code 1 because global coverage was below the repo-wide threshold.
The targeted no-coverage run passed cleanly.
```
