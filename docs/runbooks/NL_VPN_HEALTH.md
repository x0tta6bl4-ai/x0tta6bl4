# NL VPN Health Runbook

Use this runbook for the NL exit node `89.125.1.107` and the local
`singbox_tun`/v2rayN client path.

## Healthy State

- `x0tta-node.service` is active and logs `proxy=OK`.
- Local SOCKS auto-detect resolves to `127.0.0.1:10918` unless overridden.
- Route to `89.125.1.107` bypasses `singbox_tun` through the LAN gateway.
- Generic traffic, for example `1.1.1.1`, still routes through `singbox_tun`.
- NL server health-check reports `HEALTHY` for `x-ui.service`.
- `x0tta-vpn-watchdog.service` is active and exposes metrics on `127.0.0.1:9091`.
- `x0tta-vpn-boot-validate.timer` is enabled for post-reboot evidence.

## State Model

Use the local state contract for incident language:

```text
nl-diagnostics/vpn-state-contract-2026-05-27.md
```

The important distinction is:

- `ok`: VPN works and there are no meaningful warnings.
- `advisory`: VPN transport works, but there is a warning to watch.
- `degraded`: VPN is partially unstable.
- `critical`: the main VPN function is broken.
- `provider_outage`: evidence points to VPS host/provider failure.

Current NL runtime can report `mode=degraded` when Telegram media edges are
slow. That is not automatically a VPN outage. If `x-ui` is active, core
listeners are present, packet loss is zero, and transport paths are healthy,
classify it as `advisory`, not `critical`.

## Local Check

```bash
bash scripts/vpn_status.sh --check
bash scripts/vpn_status.sh --json | python3 -m json.tool
python3 scripts/vpn_provider_guard.py --json
systemctl status --no-pager --lines=20 x0tta-node.service
systemctl status --no-pager --lines=20 x0tta-vpn-watchdog.service
journalctl -u x0tta-node.service --no-pager --since "10 minutes ago" | tail -n 40
curl -fsS http://127.0.0.1:9091/metrics | sed -n '1,40p'
ip route get 89.125.1.107
ip route get 1.1.1.1
```

Expected:

```text
SOCKS5: 127.0.0.1:10918 (auto)
x0tta-node.service active
Recent health loop OK: Network OK | latency=... | proxy=OK | FIN-WAIT-2=0
Route to VPN server bypasses tunnel
Internet reachable via VPN - exit IP is VPN server: 89.125.1.107
Watchdog running - checks: ..., heals: 0
x0tta-vpn-boot-validate.timer enabled
Boot validation PASS for current boot
vpn_proxy_healthy 1
overall_status=ok
failure_domain=none
recommended_action=observe
provider_guard=allow
Result: PASS
```

## Read-Only Snapshot

When NL must not be changed, use the local collector. It writes only under
`/mnt/projects/nl-diagnostics/snapshots/` and sends only read-only commands to
NL: `systemctl`, `ss`, `sqlite3 -readonly`, `journalctl`, `cat`, `df`, `free`.

```bash
/mnt/projects/nl-diagnostics/collect_vpn_readonly_snapshot.sh
```

Classify the snapshot:

```bash
/mnt/projects/nl-diagnostics/classify_vpn_snapshot.py /mnt/projects/nl-diagnostics/snapshots/<timestamp>
```

To include local app/protocol blocking probes in the snapshot, enable them
explicitly:

```bash
VPN_ENABLE_BLOCKING_PROBES=1 /mnt/projects/nl-diagnostics/collect_vpn_readonly_snapshot.sh
```

This adds:

```text
local/blocking_probe.json
```

The probe compares direct and SOCKS paths for a small public target set. It does
not write to NL.

Default target config:

```text
nl-diagnostics/blocking_probe_targets.json
```

It includes HTTP targets and TCP targets such as Telegram media IPs on port 443.

Summarize probe history across snapshots:

```bash
python3 /mnt/projects/nl-diagnostics/summarize_blocking_probe_history.py \
  --json-out /mnt/projects/nl-diagnostics/blocking-probe-history-2026-05-28.json \
  --markdown-out /mnt/projects/nl-diagnostics/blocking-probe-history-2026-05-28.md
```

Current local trend:

```text
snapshot_count=2
trend=stable_no_probe_evidence
latest_snapshot=20260527T220219Z
latest_targets_ok=8/8
```

Expected healthy/advisory output shape:

```json
{
  "overall_status": "advisory",
  "transport_status": "healthy",
  "failure_domain": "external_network",
  "recommended_action": "observe",
  "blocking_assessment": {
    "category": "app_specific_degradation",
    "recommended_probe": "test Telegram media separately from core VPN; do not restart x-ui"
  },
  "mutation_allowed": false,
  "nl_mutation_allowed": false
}
```

Run local classifier tests after changing classification rules:

```bash
python3 /mnt/projects/nl-diagnostics/test_classify_vpn_snapshot.py
```

## Provider Evidence Packet

When provider-side failure is suspected, build a local packet from the latest
read-only snapshot:

```bash
python3 /mnt/projects/nl-diagnostics/build_provider_incident_packet.py
```

Expected output:

```text
json: /mnt/projects/nl-diagnostics/provider-incident-packets/provider-incident-packet-<timestamp>.json
markdown: /mnt/projects/nl-diagnostics/provider-incident-packets/provider-incident-packet-<timestamp>.md
```

The packet is local evidence only. It does not permit NL mutation. If
`snapshot_stale=true`, first run the read-only snapshot collector again and
rebuild the packet.

## Profile Switch Signals

If NL runtime reports:

```text
mode=anti_block
recommended_action=switch_profile
```

do not treat it as an x-ui outage by itself. First classify a fresh snapshot.
The local policy is documented here:

```text
nl-diagnostics/profile-switch-policy-2026-05-27.md
```

Rule of thumb:

```text
transport healthy/advisory + local VPN ok -> manual_profile_review
stale snapshot -> blocked_stale_snapshot
provider outage -> provider_ticket first
local client critical -> local fix first
```

No automatic profile switch is allowed by the current policy.

## Blocking / Censorship Signals

Use the blocking policy when users report that only some services fail:

```text
nl-diagnostics/blocking-response-policy-2026-05-27.md
nl-diagnostics/blocking-landscape-2026-05-27.md
```

Rule:

```text
blocking signal != x-ui restart
blocking signal != automatic profile switch
```

Interpretation examples:

```text
core VPN healthy + Telegram media degraded
= blocking_assessment.category=app_specific_degradation
= action: observe and test Telegram media separately

runtime_mode=anti_block + recommended_action=switch_profile
= blocking_assessment.category=anti_block_candidate
= action: manual profile review only

SPB disabled
= do not use SPB as fallback path
```

The classifier also treats a fresh boot gap as a warning when VPN transport is
currently healthy. In that case the provider packet uses `packet_type=provider_watch`,
not an automatic outage/restart decision.

## Boot Gap / Unclean Shutdown

If users report that VPN "did not work" but current transport is healthy, check
for a guest boot gap before restarting anything:

```bash
/mnt/projects/nl-diagnostics/collect_vpn_readonly_snapshot.sh
/mnt/projects/nl-diagnostics/classify_vpn_snapshot.py /mnt/projects/nl-diagnostics/snapshots/<timestamp>
```

Evidence files:

```text
nl/boot_history.txt
nl/last_reboots.txt
nl/current_boot_integrity.txt
nl/previous_boot_gap_indicators.txt
nl/previous_boot_tail.txt
```

Interpretation:

```text
boot gap + "uncleanly shut down" + current x-ui/listeners healthy
= provider_watch / ask provider to confirm host event

explicit "hypervisor initiated shutdown" + current VPN broken
= provider_outage / provider_ticket
```

Do not restart NL services just because a boot gap exists. First confirm current
transport status and whether the outage is still active.

## Persistent Route Bypass

The persistent bypass is installed as:

```text
/etc/systemd/system/x0tta-vpn-route-bypass.service
/etc/systemd/system/x0tta-node.service.d/10-route-bypass.conf
/usr/local/sbin/x0tta-vpn-route-bypass
/etc/systemd/system/x0tta-vpn-boot-validate.service
/etc/systemd/system/x0tta-vpn-boot-validate.timer
/usr/local/sbin/x0tta-vpn-boot-validate
```

Source files live in the repo:

```text
scripts/apply_vpn_route_bypass.sh
scripts/vpn_boot_validate.sh
infra/systemd/x0tta-vpn-route-bypass.service
infra/systemd/x0tta-node-route-bypass.conf
infra/systemd/x0tta-vpn-boot-validate.service
infra/systemd/x0tta-vpn-boot-validate.timer
```

Reapply manually:

```bash
sudo systemctl restart x0tta-vpn-route-bypass.service
ip route get 89.125.1.107
```

If `scripts/apply_vpn_route_bypass.sh` still sees `singbox_tun` in the route
to `89.125.1.107` after applying the bypass, it exits non-zero instead of
silently accepting a route loop.

## Restart/Reboot Validation

Local service restart was validated with:

```bash
sudo systemctl restart x0tta-vpn-route-bypass.service
sudo systemctl restart x0tta-node.service
bash scripts/vpn_status.sh
```

After a planned host reboot, validate the boot path with:

```bash
systemctl is-enabled x0tta-vpn-route-bypass.service x0tta-vpn-watchdog.service x0tta-node.service x0tta-vpn-boot-validate.timer
systemctl is-active x0tta-vpn-route-bypass.service x0tta-vpn-watchdog.service x0tta-node.service
systemctl status --no-pager --lines=30 x0tta-vpn-boot-validate.service
cat /var/log/x0tta6bl4/vpn_boot_validation.last
bash scripts/vpn_status.sh --check
bash scripts/vpn_status.sh --json | python3 -m json.tool
python3 scripts/vpn_provider_guard.py --json
curl -fsS http://127.0.0.1:9091/metrics | sed -n '1,40p'
```

Expected post-boot evidence:

```text
status=PASS
detail=vpn_status_check_passed
Boot validation PASS for current boot
Result: PASS
overall_status=ok
failure_domain=none
recommended_action=observe
provider_guard=allow
```

## Watchdog Metrics

The watchdog runs in metrics-first mode:

```text
/etc/systemd/system/x0tta-vpn-watchdog.service
VPN_WATCHDOG_ENABLE_HEAL=false
VPN_WATCHDOG_LOG_PATH=/var/log/x0tta6bl4/vpn_watchdog.log
```

This exposes Prometheus metrics without performing active recovery actions.
Enable active healing only after confirming it is safe for the current client:

```bash
sudo systemctl edit x0tta-vpn-watchdog.service
# set Environment=VPN_WATCHDOG_ENABLE_HEAL=true in an override
sudo systemctl restart x0tta-vpn-watchdog.service
```

When active healing is enabled, the watchdog still requires repeated failures
before it sends recovery actions:

```text
VPN_PROXY_HEAL_FAILURES=3
VPN_PACKET_LOSS_HEAL_FAILURES=2
VPN_STALE_STATE_HEAL_FAILURES=2
VPN_PREEMPTIVE_CLEANUP_FAILURES=3
```

## NL Server Check

Read-only NL checks:

```bash
ssh -o BatchMode=yes -o ConnectTimeout=10 nl 'hostname; who -b; uptime; systemctl --failed --no-pager'
ssh -o BatchMode=yes -o ConnectTimeout=10 nl 'systemctl is-active x-ui warp-svc ghost-vpn ghost-tcp-bridge ghost-access-nl-beta nginx docker'
ssh -o BatchMode=yes -o ConnectTimeout=10 nl 'ss -lntup | egrep ":(443|2083|39829|2443|4433|4434|51820|8443|62789)" || true'
ssh -o BatchMode=yes -o ConnectTimeout=10 nl 'sqlite3 -readonly /etc/x-ui/x-ui.db "select id,port,protocol,enable,remark from inbounds order by port;"'
ssh -o BatchMode=yes -o ConnectTimeout=10 nl 'cat /opt/x0tta6bl4-mesh/state/runtime-state.json'
```

Do not treat local `x0tta6bl4-xray-vps/configs/server-config.json` as the
production NL source of truth. Real NL production state is:

```text
NL:/etc/systemd/system/x-ui.service
NL:/usr/local/x-ui/bin/config.json
NL:/etc/x-ui/x-ui.db
NL:/opt/x0tta6bl4-mesh/state/runtime-state.json
NL:/opt/ghost-access-bot/current/
```

The standalone `xray.service` is not the active NL production service; NL uses
`x-ui.service` to run Xray.

The x-ui-aware health-check below writes a report file under `LOG_DIR`. Use it
only when writing to NL is allowed:

```bash
ssh -o BatchMode=yes -o ConnectTimeout=10 nl \
  'LOG_DIR=/tmp bash -s' < x0tta6bl4-xray-vps/scripts/health-check.sh
```

Expected:

```text
Overall Status: HEALTHY
Xray service: x-ui
Xray config: /usr/local/x-ui/bin/config.json
```

## Safe Heal

Use only after the local check shows proxy failure or stale TCP states:

```bash
bash scripts/vpn_heal.sh
sudo systemctl restart x0tta-node.service
```

`scripts/vpn_heal.sh` runs a preflight first. If SOCKS5 is healthy and there
are no `FIN-WAIT-2`/`CLOSE-WAIT` connections to the NL server, it exits without
sending `SIGHUP` to `xray`. To force a reload anyway:

```bash
VPN_HEAL_FORCE=1 bash scripts/vpn_heal.sh
```

Before any local mutation, `vpn_heal.sh` calls:

```bash
python3 scripts/vpn_provider_guard.py --check
```

When `VPN_HEAL_FORCE=1` is set, the script requires fresh local snapshot
evidence by default and passes `--require-fresh`. The default freshness limit is
3600 seconds. Override the limit only when you understand the incident context:

```bash
VPN_PROVIDER_GUARD_MAX_AGE_SECONDS=900 VPN_HEAL_FORCE=1 bash scripts/vpn_heal.sh
```

If the guard blocks, `vpn_heal.sh` exits before `ss -K` and before sending
`SIGHUP` to local `xray`. Manual override exists, but use it only for a known
local-client problem:

```bash
VPN_HEAL_IGNORE_PROVIDER_GUARD=1 bash scripts/vpn_heal.sh
```

The self-healing daemon does not rotate Reality credentials unless
`VPN_ENABLE_REALITY_ROTATION=true` is explicitly set.
It also does not switch pulse profiles unless `VPN_ENABLE_PULSE_SHIFT=true`
is explicitly set.
Active recovery actions in `self_healing_daemon.py` are disabled by default;
set `VPN_SELF_HEAL_ENABLE=true` only after the local check is stable and the
operator accepts automatic `ss -K`/`SIGHUP` recovery.

The watchdog does not send `SIGTERM` to local `xray` by default. That hard-heal
step needs a separate flag and fresh provider-guard evidence:

```bash
VPN_WATCHDOG_ENABLE_HEAL=true VPN_WATCHDOG_ALLOW_HARD_HEAL=1 python3 src/network/vpn_watchdog.py
```

Use this only for a confirmed local-client fault. It is not a fix for NL
provider outage, host overload, or Telegram media edge latency.

## Rollback

Dry-run the rollback first. This prints the commands without changing the
running VPN:

```bash
bash scripts/rollback_nl_vpn_route_bypass.sh --dry-run
```

Apply the rollback only when the operator accepts the impact:

```bash
sudo bash scripts/rollback_nl_vpn_route_bypass.sh --apply
```

By default, the rollback does not restart `x0tta-node.service`; pass
`--restart-node` only when a short client interruption is acceptable.

Manual equivalent:

```bash
sudo systemctl disable --now x0tta-vpn-route-bypass.service
sudo systemctl disable --now x0tta-vpn-watchdog.service
sudo systemctl disable --now x0tta-vpn-boot-validate.timer
sudo systemctl stop x0tta-vpn-boot-validate.service
sudo rm -f /etc/systemd/system/x0tta-vpn-route-bypass.service
sudo rm -f /etc/systemd/system/x0tta-vpn-watchdog.service
sudo rm -f /etc/systemd/system/x0tta-vpn-boot-validate.service
sudo rm -f /etc/systemd/system/x0tta-vpn-boot-validate.timer
sudo rm -f /etc/systemd/system/x0tta-node.service.d/10-route-bypass.conf
sudo rm -f /usr/local/sbin/x0tta-vpn-route-bypass
sudo rm -f /usr/local/sbin/x0tta-vpn-boot-validate
sudo systemctl daemon-reload
sudo ip rule del priority 8999 to 89.125.1.107/32 lookup main 2>/dev/null || true
sudo ip route del 89.125.1.107/32 2>/dev/null || true
```

Then restart the node service only if required:

```bash
sudo systemctl restart x0tta-node.service
```

After rollback, always check:

```bash
ip route get 89.125.1.107
bash scripts/vpn_status.sh --check
```

If the route to `89.125.1.107` points to `singbox_tun`, rollback has exposed a
route loop. Reapply the bypass before restarting VPN clients.
