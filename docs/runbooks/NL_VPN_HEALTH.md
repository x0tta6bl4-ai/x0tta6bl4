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

For an incident, prefer the one-command read-only refresh:

```bash
VPN_ENABLE_BLOCKING_PROBES=1 /mnt/projects/nl-diagnostics/run_vpn_incident_readonly_refresh.sh
```

Expected:

```text
snapshot=/mnt/projects/nl-diagnostics/snapshots/<timestamp>
refresh=/mnt/projects/nl-diagnostics/vpn-planning-refresh-2026-05-28.md
```

It collects a fresh read-only snapshot and rebuilds the local planning reports.
It does not write to NL.
When `/mnt/projects/.tmp` exists, the incident wrapper and refresh runner use it
as `TMPDIR` for child commands so local diagnostics do not depend on `/tmp`
having free space.

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
snapshot_count=5
trend=stable_no_probe_evidence
latest_snapshot=20260528T000600Z
latest_targets_ok=8/8
```

Build the current operator decision from the latest snapshot and probe history:

To refresh all local planning reports from an existing snapshot:

```bash
python3 /mnt/projects/nl-diagnostics/refresh_vpn_planning_reports.py \
  --snapshot /mnt/projects/nl-diagnostics/snapshots/<timestamp>
```

Current refresh report:

```text
nl-diagnostics/vpn-planning-refresh-2026-05-28.md
```

Expected:

```text
ok=true
decision=observe
operator_status=observe
boot_gap_watch_status=watch
boot_gap_seconds=21907
provider_packet_type=provider_watch
provider_packet_stale=False
provider_packet_snapshot_age_seconds=<varies with time; collect a fresh snapshot after 3600>
blocking_history_trend=stable_no_probe_evidence
blocking_history_snapshot_count=5
manual_failover_status=planning_not_active
manual_failover_readiness_status=blocked_no_incident_trigger
manual_failover_probe_allowed=False
manual_failover_switch_allowed=False
secondary_candidate_score_status=missing_candidates
secondary_candidate_viable_count=0
secondary_exit_requirements_status=requirements_ready_no_candidate
secondary_exit_requirements_missing=NET-01
local_diagnostic_environment_status=watch_root_full_tmpdir_available
local_root_status=critical_full
local_tmpdir_writable=True
local_recommended_tmpdir_prefix=TMPDIR=/mnt/projects/.tmp
nl_transport_probe_status=healthy
nl_transport_probe_ok_count=3/3
nl_transport_uptime_status=stable_healthy
nl_transport_uptime_samples=11
nl_transport_uptime_bad_streak=0
secondary_probe_template_status=planning_template
readiness_audit_status=ready_local_with_future_blocks
readiness_missing=0
incident_timeline_event_count=9
incident_timeline_latest_type=provider_watch
incident_timeline_latest_snapshot=20260528T000600Z
nl_mutation_allowed=false
spb_fallback_allowed=false
```

Readiness audit:

```text
nl-diagnostics/vpn-plan-readiness-audit-2026-05-28.md
```

Current audit summary:

```text
ready_local=15
blocked_future_approval=3
watch=2
missing=0
watch_items=BOOT-01, LOCALENV-01
blocked_items=FAILOVER-03, GATE-01, FAILOVER-02
```

Interpretation: the local observe-mode plan is usable now. Future NL writes and
a real secondary exit node remain blocked until separate approval/setup. Manual
failover is also blocked while the current decision is `observe` and no healthy
non-NL/non-SPB secondary node exists.

Local diagnostic environment:

```text
nl-diagnostics/local-diagnostic-environment-2026-05-28.md
```

Current rule:

```text
status=watch_root_full_tmpdir_available
root_status=critical_full
root_free_gib=0.0
diagnostic_tmpdir=/mnt/projects/.tmp
diagnostic_tmpdir_writable=true
recommended_tmpdir_prefix=TMPDIR=/mnt/projects/.tmp
```

Interpretation: local diagnostics can continue, but commands that create
temporary files should be run with `TMPDIR=/mnt/projects/.tmp` until `/` is
cleaned. The refresh runner now passes this `TMPDIR` to its child commands by
default when the variable is not already set. Do not delete
`/tmp/antigravity_restore*` without separate local cleanup approval.

Outside-in NL transport probe:

```text
nl-diagnostics/nl-transport-probe-2026-05-28.md
```

Current result:

```text
89.125.1.107:443 ok
89.125.1.107:2083 ok
89.125.1.107:39829 ok
status=healthy
recommended_action=observe
```

Transport uptime history:

```text
nl-diagnostics/nl-transport-uptime-summary-2026-05-28.md
nl-diagnostics/nl-transport-uptime-history.jsonl
```

Current result:

```text
status=stable_healthy
sample_count=11
latest_status=healthy
consecutive_non_healthy=0
```

Local uptime scheduler templates are prepared but not installed:

```text
infra/systemd/x0tta-vpn-nl-transport-uptime.service
infra/systemd/x0tta-vpn-nl-transport-uptime.timer
```

What they would do if installed on the local host:

```text
run the outside-in NL TCP probe every 5 minutes
append/update local uptime evidence under /mnt/projects/nl-diagnostics/
set TMPDIR=/mnt/projects/.tmp for local temporary files
perform no SSH, no NL writes, no SPB fallback, and no service restart
```

Future local-host install commands, only after separate local approval:

```bash
sudo install -m 0644 infra/systemd/x0tta-vpn-nl-transport-uptime.service /etc/systemd/system/
sudo install -m 0644 infra/systemd/x0tta-vpn-nl-transport-uptime.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now x0tta-vpn-nl-transport-uptime.timer
```

These commands are for the local diagnostic host, not for NL.

Boot-gap watch:

```text
nl-diagnostics/boot-gap-watch-2026-05-28.md
```

Current result:

```text
status=watch
boot_gap_seconds=21907
provider_status=recent_boot_gap
transport_status=healthy
recommended_action=observe provider signal; do not restart NL while transport is healthy/advisory
```

Provider packet for the same snapshot:

```text
nl-diagnostics/provider-incident-packets/provider-incident-packet-20260528T000600Z.md
```

Current packet:

```text
packet_type=provider_watch
snapshot_stale=false
snapshot_age_seconds=<varies with time; collect fresh evidence after 3600>
NL writes=0
```

Incident timeline:

```text
nl-diagnostics/vpn-incident-timeline-2026-05-28.md
```

Current timeline:

```text
event_count=9
latest_event_type=provider_watch
latest_snapshot=20260528T000600Z
```

Freshness rule:

```text
snapshot_age_seconds <= 3600 -> fresh evidence
snapshot_age_seconds > 3600 -> collect a new read-only snapshot before action
```

For the shortest incident checklist, open:

```text
nl-diagnostics/vpn-operator-card-2026-05-28.md
```

```bash
python3 /mnt/projects/nl-diagnostics/build_vpn_decision_report.py \
  --snapshot /mnt/projects/nl-diagnostics/snapshots/<timestamp> \
  --json-out /mnt/projects/nl-diagnostics/current-vpn-decision-2026-05-28.json \
  --markdown-out /mnt/projects/nl-diagnostics/current-vpn-decision-2026-05-28.md
```

Current decision:

```text
decision=observe
confidence=high
reason=core VPN is healthy/advisory and blocking probes show no direct-vs-SOCKS failure
```

Build the improvement backlog from the same evidence:

```bash
python3 /mnt/projects/nl-diagnostics/build_vpn_improvement_backlog.py \
  --json-out /mnt/projects/nl-diagnostics/vpn-improvement-backlog-2026-05-28.json \
  --markdown-out /mnt/projects/nl-diagnostics/vpn-improvement-backlog-2026-05-28.md
```

Current backlog split:

```text
local_now: LOCAL-01, LOCAL-02, LOCAL-03, LOCAL-04
future_nl_write: NL-FUTURE-01, NL-FUTURE-02
future_resilience: FUTURE-RESILIENCE-01
spb_fallback_allowed=false
```

Manual failover planning:

```text
nl-diagnostics/manual-failover-plan-2026-05-28.md
nl-diagnostics/manual-failover-readiness-2026-05-28.md
nl-diagnostics/secondary-exit-candidate-score-2026-05-28.md
nl-diagnostics/secondary-exit-requirements-2026-05-28.md
```

Current rule:

```text
manual_failover_status=planning_not_active
manual_failover_readiness_status=blocked_no_incident_trigger
manual_probe_allowed=false
manual_switch_allowed=false
secondary_candidate_score_status=missing_candidates
secondary_candidate_viable_count=0
secondary_exit_requirements_status=requirements_ready_no_candidate
secondary_exit_requirements_missing=NET-01
automatic_failover_allowed=false
spb_fallback_allowed=false
secondary exit node must be new provider/region, not NL and not SPB
```

Secondary health probe template:

```bash
python3 /mnt/projects/nl-diagnostics/create_secondary_exit_config.py \
  --label emergency-1 \
  --provider <new-provider> \
  --region <new-region> \
  --host <secondary-host-or-ip> \
  --tcp-port 443 \
  --out /mnt/projects/.tmp/secondary-exit-probe.json
```

```bash
python3 /mnt/projects/nl-diagnostics/probe_secondary_exit.py \
  --config /mnt/projects/.tmp/secondary-exit-probe.json
```

Expected template result before a secondary node exists:

```text
status=planning_template
candidate_configured=false
nl_mutation_allowed=false
spb_fallback_allowed=false
```

The config generator rejects the current NL IP, SPB markers, VPN URIs, UUIDs,
private keys, and bot tokens.

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
