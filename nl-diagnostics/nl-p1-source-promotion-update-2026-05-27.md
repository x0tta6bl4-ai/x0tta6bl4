# NL P1 Source Promotion Update, 2026-05-27

## Status

NL remained read-only.

No deploy, no restart, no `scp` to NL, no x-ui DB/config write, no systemd
change.

## Promoted Locally

Latest update: four more P1 runtime files and one P2 monitor were promoted from local quarantine
into reviewed local source:

```text
services/nl-server/ghost-access/sync_xray_device_activity.py
services/nl-server/ghost-vpn/ghost_tcp_bridge.py
services/nl-server/ghost-vpn/ghost_vpn_server.py
services/nl-server/ghost-vpn/ghost_vpn_client.py
services/nl-server/mesh-runtime/auto_monitor.py
```

Their hashes match the current NL profile source hashes:

```text
sync_xray_device_activity.py 2d716478bd8a3c6926c315ae476173934d4cd310433c831c3f0dd20c4e1db745
ghost_tcp_bridge.py          f2d6cfb176ded07b305f0794f2a5abbc678ac498821e5741e1fe5ce73194ba06
ghost_vpn_server.py          d51a7a742d8a73a81d40dfa9cc4c782a5fff1642aa1461b5c96c3777ee898b1e
ghost_vpn_client.py          f214ee0990f5833b42545efc9e8d3c49db05912778f24455a900243fa9f85510
auto_monitor.py              904007827c4e1203ac2dac8f0974dee19d37fb6c84c41a511588a5f588a96671
```

Manifest update:

```text
promoted_count: 13
nl_write_allowed: false
deployable_to_nl: false
```

## Gap Impact

Fresh gap analysis after promotion:

```json
{
  "local_name_drift": 7,
  "missing_local_source": 5,
  "redacted_review_only": 2,
  "same_hash_elsewhere": 12,
  "server_backup_only": 4,
  "server_runtime_artifact": 4
}
```

Before this step:

```text
missing_local_source: 6
same_hash_elsewhere: 11
```

## Local Tests Added

```text
services/nl-server/tests/test_listener_and_profile_hint.py
services/nl-server/tests/test_activity_sync_and_tcp_bridge.py
services/nl-server/tests/test_ghost_vpn_runtime_source.py
services/nl-server/tests/test_auto_monitor_source.py
```

Covered behavior:

```text
listener missing -> ANOMALY_DETECTED
healthy listener -> BASELINE_OK
TCP symptom pattern -> ANOMALY_DETECTED
degraded mode -> anti-block-public-ingress, non-443 ports
advisory mode -> stable-primary, 443
fallback mode -> ghost-fallback, 4433/4434
missing/invalid runtime-state -> empty state
Xray access-log email/IP extractors
x-ui last_online/latest IP helpers
activity sync cursor skips already processed lines
missing access log is non-fatal warning
UDP response framing for TCP bridge
closing TCP writer drops UDP response
GhostVPN server handshake rate limiting
GhostVPN server cookie context binding
GhostVPN client route helper logic
GhostVPN TCP transport frame encoding
auto_monitor alert suffix formatting
auto_monitor alert retention limit
auto_monitor static mutation-command guard
```

## Remaining P1 Work

Still not promoted as deployable source:

```text
health_check.sh                       mutating restart logic
run_vpn_delivery_canary.py            can mutate canary/runtime users
run_vpn_service_access_agent.py       status semantics need tests/fix
xray_runtime_user_manager.py          mutates Xray runtime users
xui_client_manager.py                 writes x-ui DB
ghost_vpn_protocol.py                 local version intentionally differs
```

Next safe local work:

```text
review remaining Ghost Access mutating tools;
do not deploy class C GhostVPN server/client until dry-run, backup and rollback gates exist.
```
