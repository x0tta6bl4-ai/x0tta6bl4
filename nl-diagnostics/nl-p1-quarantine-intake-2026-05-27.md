# NL P1 Quarantine Intake, 2026-05-27

## Status

NL remained read-only from the server side.

The only remote action was:

```text
ssh nl cat <source file>
```

No `systemctl`, restart, scp-to-NL, sqlite write, cron/timer edit, or x-ui change
was performed.

Local intake batch:

```text
services/nl-server/.quarantine/incoming/20260527T055602Z
```

Result:

```text
accepted: 13
blocked by secret-pattern scan: 0
```

The quarantine directory is git-ignored. Files there are not deployable source.

## Validation

Checks run locally:

```text
python3 -m py_compile services/nl-server/tools/pull_candidate_readonly.py
python3 services/nl-server/tools/pull_candidate_readonly.py --priority P1
python3 services/nl-server/tools/pull_candidate_readonly.py --priority P1 --pull
python3 -m py_compile services/nl-server/.quarantine/incoming/20260527T055602Z/mesh-runtime/*.py
python3 -m py_compile services/nl-server/.quarantine/incoming/20260527T055602Z/ghost-access/*.py
python3 -m py_compile services/nl-server/.quarantine/incoming/20260527T055602Z/ghost-vpn/*.py
bash -n services/nl-server/.quarantine/incoming/20260527T055602Z/mesh-runtime/health_check.sh
```

Secret scan:

```text
strict URI/key/token assignment scan: no hits
```

## Pulled P1 Files

```text
mesh-runtime/build_runtime_state.py             497 bytes
mesh-runtime/listener_loss_signal.py           2960 bytes
mesh-runtime/publish_client_profile_hint.py    2561 bytes
mesh-runtime/health_check.sh                   1789 bytes
ghost-access/run_vpn_delivery_canary.py       15454 bytes
ghost-access/run_vpn_service_access_agent.py  35511 bytes
ghost-access/sync_xray_device_activity.py      8904 bytes
ghost-access/xray_runtime_user_manager.py      6715 bytes
ghost-access/xui_client_manager.py            14974 bytes
ghost-vpn/ghost_vpn_server.py                 50654 bytes
ghost-vpn/ghost_vpn_client.py                 53583 bytes
ghost-vpn/ghost_vpn_protocol.py               27919 bytes
ghost-vpn/ghost_tcp_bridge.py                  2484 bytes
```

## Hash Comparison Against Local Workspace

Current NL quarantine hash:

```text
mesh-runtime/health_check.sh
  NL:    3b70430c20c8b828834fc01fc772cb09e149dd3c355fe59f782f9829d71f2590
  local: 1b9243ecc2c64c32acb1e6b9f8e55f41640281b9390ab18e5776f0811a20d82c
  old backup: same as local

ghost-access/run_vpn_delivery_canary.py
  NL:         269fb1d88cf6e88f79c020682686019cbb829399aaf98d6ca1a46d36c8f7e050
  old backup: 41341b6a5b05add41682a5487b90d68ff5123aa5fbb9f7959c83f14069b9b95b

ghost-access/run_vpn_service_access_agent.py
  NL:         41b6a912e5c02e294777f517206651cd5712a470651b4fc9a948712a7291ee7f
  old backup: b3fdea271bb4c7faac018c1cb6869a9f48c121f29885ed8cd130046de16ff244

ghost-access/xray_runtime_user_manager.py
  NL:         3802f64e80e43fd8bdcf36afab6636b7b8a157ec018b2328d1ee258d517c08b4
  old backup: b0f5274e324bc92a2335d4eefd7766bfcfb3a8f88e1f2fc216bfbe7d0d1047a9

ghost-access/xui_client_manager.py
  NL:         104acccf5ef345e17f7b64c9e85975c2f35b20900b90c291922a3f81b2248769
  old backup: faa48ac7d792fe534e2ae80e72502a4deff827e3982b8a2673d3ca17e1ed84a5
```

Ghost VPN P1 files were missing from the local workspace:

```text
src/network/ghost_vpn_server.py
src/network/ghost_vpn_client.py
src/network/ghost_vpn_protocol.py
scripts/ghost_tcp_bridge.py
```

## Key Findings

### 1. Real NL health scripts are not purely read-only

`mesh-runtime/health_check.sh` can restart `x-ui`:

```text
systemctl restart x-ui
```

It also writes restart cooldown state under:

```text
/opt/x0tta6bl4-mesh/state/restart-cooldown.json
```

Current cooldown in the pulled source:

```text
RESTART_COOLDOWN_SEC=600
```

This is only 10 minutes. The improvement plan target is 30 minutes minimum for
NL restart actions. Future work should split this into:

```text
health_check_readonly.sh
health_heal_xui.sh
```

and require an explicit mutation flag before any restart.

### 2. The false `degraded` meaning exists in the real NL source

`run_vpn_service_access_agent.py` returns top-level `degraded` when Telegram media
status is `degraded`, even when transport is healthy:

```text
telegram_status == degraded -> overall_status degraded
```

This matches the observed problem: a Telegram media edge issue can make the whole
runtime look degraded even while VPN transport is usable.

The local classifier now works around this by separating:

```text
transport_status
telegram_media_status
overall_status
failure_domain
recommended_action
```

Future NL source fix should make Telegram-only degradation an `advisory` overall
state when transport paths are healthy.

### 3. Some Ghost Access "checks" can mutate x-ui or runtime users

These files need review before promotion:

```text
run_vpn_delivery_canary.py
xray_runtime_user_manager.py
xui_client_manager.py
```

Observed behavior from source structure:

```text
xui_client_manager.py writes /etc/x-ui/x-ui.db
xray_runtime_user_manager.py talks to Xray HandlerService gRPC
run_vpn_delivery_canary.py can ensure a canary client and run a local Xray probe
```

These are useful, but they must not be mixed with read-only diagnostics.

### 4. Ghost VPN code mutates network stack

Ghost VPN server/client source uses:

```text
sysctl net.ipv4.ip_forward=1
iptables NAT/FORWARD rules
ip rule add/del
ip route add/del
TUN interfaces
```

That is expected for a VPN, but it means Ghost VPN needs its own preflight,
rollback, and privilege model. It should not be called by generic health checks.

### 5. P2 source is still needed

`mesh-runtime/build_runtime_state.py` is only a wrapper around:

```text
vps_build_runtime_state.py
```

That file is still a P2 candidate, not pulled in this P1 batch. Until P2 intake is
reviewed, the exact NL runtime-state generation logic is not fully represented
locally.

## Recommendation

Next local-only work:

```text
1. pull P2 source into quarantine with the same read-only tool;
2. create a promotion checklist per file: read-only, writes state, writes x-ui DB, restarts service, changes network stack;
3. promote only read-only observability files first;
4. write tests for `run_vpn_service_access_agent.py` status semantics before changing NL;
5. prepare a separate mutation-gated heal script for x-ui restarts.
```

No NL deploy is recommended yet.
