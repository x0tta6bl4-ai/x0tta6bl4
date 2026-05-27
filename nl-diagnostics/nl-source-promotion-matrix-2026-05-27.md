# NL Source Promotion Matrix, 2026-05-27

## Status

This matrix is based on local quarantine intake only.

NL write permission:

```text
false
```

Sixteen files have been promoted from quarantine into local reviewed source.

Important:

```text
deployable_to_nl: false
NL writes: 0
```

## Promotion Classes

```text
A = promote first after review; observability/control-plane only
B = promote with tests; writes local state/logs but does not restart services
C = mutating operational tool; requires dry-run, backup, rollback, explicit flag
D = blocked/sensitive; manual redaction workflow only
```

## Matrix

| File | Class | Why |
|---|---:|---|
| `mesh-runtime/build_runtime_state.py` | A | Wrapper only, but depends on `vps_build_runtime_state.py`. |
| `mesh-runtime/listener_loss_signal.py` | B | Reads `ss`, writes listener signal JSON under `/opt/x0tta6bl4-mesh/state`. |
| `mesh-runtime/publish_client_profile_hint.py` | B | Reads runtime-state and writes client hint JSON. |
| `mesh-runtime/vps_build_runtime_state.py` | B | Core runtime-state generator; writes state JSON and needs status semantics tests. |
| `mesh-runtime/profile_status_api.py` | A | Serves runtime-state/profile hint over localhost HTTP. |
| `mesh-runtime/monitor.py` | B | Exposes Prometheus metrics from runtime-state. |
| `mesh-runtime/auto_monitor.py` | B | Writes alert log and currently treats `mode=degraded` as warning. |
| `mesh-runtime/health_check.sh` | C | Can run `systemctl restart x-ui`; cooldown is 600 sec. |
| `mesh-runtime/apply_config_auto.py` | C | Writes `/usr/local/x-ui/bin/config.json`. |
| `mesh-runtime/full_stealth_config.py` | C | Writes x-ui generated config and rotation state. |
| `mesh-runtime/rotation_timer.sh` | C | Sends signal to Xray process after rotation. |
| `ghost-access/run_vpn_service_access_agent.py` | B | Writes reports; currently maps Telegram-only degraded into overall degraded. |
| `ghost-access/run_vpn_delivery_canary.py` | C | Can ensure canary client and run runtime user changes. |
| `ghost-access/sync_xray_device_activity.py` | B | Reads x-ui DB/logs and syncs activity state. |
| `ghost-access/xray_runtime_user_manager.py` | C | Mutates Xray runtime users via HandlerService gRPC. |
| `ghost-access/xui_client_manager.py` | C | Writes `/etc/x-ui/x-ui.db`. |
| `ghost-access/check_bot_user_chains.py` | A | Static/source check for bot code paths. |
| `ghost-access/run_telegram_bot_simple.sh` | B | Service wrapper; requires env token at runtime but contains no token value. |
| `ghost-access/sync_spb_standalone_clients.py` | C | Writes remote SPB xray config and restarts remote xray. |
| `ghost-access/issue_offline_subscription.py` | D | Redacted review copy exists; raw source not saved; not deployable. |
| `ghost-access/telegram_bot_simple.py` | D | Redacted review copy exists; raw source not saved; not deployable. |
| `ghost-vpn/ghost_vpn_protocol.py` | A | Protocol/session structures; no service mutation by itself. |
| `ghost-vpn/ghost_tcp_bridge.py` | B | Runtime bridge process; opens sockets. |
| `ghost-vpn/ghost_vpn_server.py` | C | Changes TUN, sysctl, iptables, metrics server. |
| `ghost-vpn/ghost_vpn_client.py` | C | Changes TUN, routes, ip rules. |

## First Promotion Set

Promoted locally after first review, without deploying to NL:

```text
mesh-runtime/build_runtime_state.py
mesh-runtime/apply_config_auto.py
mesh-runtime/full_stealth_config.py
mesh-runtime/rotation_timer.sh
mesh-runtime/listener_loss_signal.py
mesh-runtime/publish_client_profile_hint.py
mesh-runtime/vps_build_runtime_state.py
mesh-runtime/profile_status_api.py
mesh-runtime/monitor.py
mesh-runtime/auto_monitor.py
ghost-access/check_bot_user_chains.py
ghost-access/sync_xray_device_activity.py
ghost-vpn/ghost_vpn_protocol.py
ghost-vpn/ghost_tcp_bridge.py
ghost-vpn/ghost_vpn_server.py
ghost-vpn/ghost_vpn_client.py
```

Current local test coverage:

```text
python3 services/nl-server/tests/test_vps_build_runtime_state.py
python3 services/nl-server/tests/test_profile_status_and_ghost_protocol.py
python3 services/nl-server/tests/test_listener_and_profile_hint.py
python3 services/nl-server/tests/test_activity_sync_and_tcp_bridge.py
python3 services/nl-server/tests/test_ghost_vpn_runtime_source.py
python3 services/nl-server/tests/test_auto_monitor_source.py
python3 services/nl-server/tests/test_apply_config_auto_source.py
python3 services/nl-server/tests/test_full_stealth_config_source.py
python3 services/nl-server/tests/test_rotation_timer_source.py
python3 services/nl-server/tests/test_templates.py
```

Covered now:

```text
healthy transport + telegram degraded -> advisory/observe
telegram degraded + unknown transport -> degraded/operator_review
x-ui inactive + ghost ready -> fallback/switch_fallback
x-ui inactive + ghost not ready -> degraded/restart_primary
real NL ports 443/2083/39829 are discovered from x-ui config shape
missing config falls back to 443/2083/39829
hot-path summary uses 2083 as secondary and 2443 as nl-beta fallback
listener-loss confidence scoring and anomaly classification
profile-hint selection for degraded/advisory/fallback modes
profile_status_api builds sanitized health from local JSON state files
profile_status_api treats missing/invalid JSON as empty state
ghost_vpn_protocol protected message round trip and tamper reject
ghost_vpn_protocol handshake init/response round trips
ghost_vpn_protocol strategy/profile switch round trips
sync_xray_device_activity access-log email/IP extraction
sync_xray_device_activity x-ui timestamp/latest-IP helpers
sync_xray_device_activity state cursor behavior and missing-log warning
ghost_tcp_bridge UDP response length-prefix framing
ghost_vpn_server handshake rate-limit and cookie context helpers
ghost_vpn_client route helper and TCP transport framing logic
auto_monitor alert formatting, retention, and mutation-command guard
apply_config_auto pure config transformations without x-ui writes
full_stealth_config rotation helpers and static mutation guard
rotation_timer shell syntax and static mutation guard
nl-beta-2443 redacted template shape and secret-pattern guard
```

Still needed before any deploy:

```text
HTTP handler test for profile_status_api endpoints
operator approval and backup/rollback gates
```

## Do Not Deploy Or Run Yet

These need mutation gates first:

```text
health_check.sh
apply_config_auto.py
full_stealth_config.py
rotation_timer.sh
run_vpn_delivery_canary.py
xray_runtime_user_manager.py
xui_client_manager.py
sync_spb_standalone_clients.py
ghost_vpn_server.py
ghost_vpn_client.py
```

Required gates:

```text
--dry-run
--force or explicit mutation env var
backup command
rollback command
30 minute cooldown for service restarts
provider overload guard
fresh read-only snapshot before and after
```

## Sensitive Redacted Files

These were intentionally not saved as raw source:

```text
issue_offline_subscription.py
telegram_bot_simple.py
```

Redacted local review copies now exist:

```text
services/nl-server/redacted/ghost-access/issue_offline_subscription.redacted.py
services/nl-server/redacted/ghost-access/telegram_bot_simple.redacted.py
nl-diagnostics/nl-redacted-source-review-2026-05-27.md
```

They remain class D. The next safe step is source reconstruction: keep code
structure and tests locally, move real VPN links/tokens/keys to runtime secrets,
and do not deploy the redacted files.
