# Blocking Response Policy, 2026-05-27

Status: local policy only. No NL or SPB writes are allowed by this document.

This policy translates the current blocking landscape into VPN incident rules.

## Core Rule

A blocking signal is not a restart signal.

Do not restart `x-ui`, rotate Reality settings, switch profiles, or use SPB just
because one app is slow or one service refuses VPN traffic.

## Categories

`classify_vpn_snapshot.py` now emits `blocking_assessment`:

```json
{
  "category": "app_specific_degradation",
  "confidence": "medium",
  "mutation_allowed": false,
  "nl_mutation_allowed": false,
  "auto_profile_switch_allowed": false,
  "recommended_probe": "test Telegram media separately from core VPN; do not restart x-ui"
}
```

Meanings:

```text
none                         no blocking-specific signal
app_specific_degradation     core VPN works, but one app/media path is degraded
anti_block_candidate         NL runtime asks for anti-block/profile review
external_network_degradation packet loss/path problem outside NL service health
exit_ip_or_vpn_rejected      direct works, VPN/SOCKS path is rejected
possible_local_isp_block     direct fails, VPN/SOCKS path works
vpn_path_degraded            direct works, VPN/SOCKS path fails
local_client_issue           fix local route/SOCKS/client first
nl_service_issue             inspect NL service/listeners read-only first
provider_or_host_issue       build provider packet first
```

## Russia-Specific Practical Rules

Use these assumptions for incident handling:

- Protocol or DPI blocking can look like a working tunnel with selected apps
  failing.
- A Russian site or app can reject known VPN/proxy exits even if the VPN tunnel
  is healthy.
- Mobile and fixed-line ISPs can behave differently.
- Telegram calls/media can degrade while generic HTTPS still works.
- TSPU/provider behavior can change without NL service changes.

Therefore:

```text
core transport healthy + one app degraded -> app_specific_degradation / observe
runtime anti_block + transport healthy -> anti_block_candidate / manual review
exit IP correct + Russian app rejects access -> exit-IP/app policy suspicion, not x-ui outage
direct fails + SOCKS works -> local ISP/path filtering suspicion
direct works + SOCKS fails -> VPN/proxy path review, not automatic NL restart
provider boot gap or hypervisor evidence -> provider_or_host_issue / provider packet
local route loop or SOCKS failure -> local_client_issue / local heal path
```

## Required Evidence Before Any Profile Change

```text
fresh read-only snapshot
local vpn_status JSON
route to NL endpoint
NL listeners and active services
runtime-state summary
provider status
blocking_assessment
manual approval
```

Automatic profile switching remains disabled.

## Probe Command

Run app/path probes manually:

```bash
python3 nl-diagnostics/probe_blocking_paths.py
```

Or include them in the read-only evidence bundle:

```bash
VPN_ENABLE_BLOCKING_PROBES=1 nl-diagnostics/collect_vpn_readonly_snapshot.sh
```

The probe writes local JSON only when it is part of a snapshot. It compares
direct and SOCKS paths by default; HTTP proxy is included only when
`VPN_HTTP_PROXY_URL` or `VPN_AGENT_PROXY_URL` is configured.

Default extended targets live here:

```text
nl-diagnostics/blocking_probe_targets.json
```

They include baseline HTTP, Telegram web/API, Telegram media TCP, OpenAI API,
GitHub, and a Russian search page.

Build local history from all saved probe snapshots:

```bash
python3 nl-diagnostics/summarize_blocking_probe_history.py \
  --json-out nl-diagnostics/blocking-probe-history-2026-05-28.json \
  --markdown-out nl-diagnostics/blocking-probe-history-2026-05-28.md
```

Latest history result:

```text
snapshot_count=3
trend=stable_no_probe_evidence
latest_snapshot=20260527T221810Z
latest_targets_ok=8/8
degraded_targets=0
```

## What Not To Do

Do not:

- use SPB as fallback while SPB is disabled;
- restart `x-ui` for Telegram-only degradation;
- rotate Reality keys because one site rejects the exit IP;
- treat `recommended_action=switch_profile` as an automatic command;
- change NL without backup, rollback plan, and explicit approval.

## Current Expected Interpretation

Latest local classification:

```text
overall_status=advisory
failure_domain=external_network
recommended_action=observe
blocking_assessment.category=app_specific_degradation
blocking_assessment.recommended_probe=test Telegram media separately from core VPN; do not restart x-ui
blocking_probe_history.trend=stable_no_probe_evidence
current_vpn_decision=observe
```

No NL or SPB writes were performed.
