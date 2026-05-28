# VPN Incident Symptom Intake

generated_at: `2026-05-28T03:26:57.349721+00:00`
status: `symptom_intake_ready_observe`
ok: `true`

## Summary

```text
decision=observe
operator_status=observe
transport_status=advisory
failure_domain=external_network
provider_status=recent_boot_gap
blocking_history_trend=stable_no_probe_evidence
blocking_history_snapshot_count=10
latest_blocking_targets_ok=8/8
nl_transport_probe_status=healthy
manual_failover_readiness_status=blocked_no_incident_trigger
manual_switch_allowed=false
required_field_count=12
allowed_field_count=12
forbidden_material_count=12
triage_group_count=6
nl_write_allowed=false
spb_fallback_allowed=false
automatic_failover_allowed=false
```

## Required Fields

- `visible_time_local`
- `affected_app_or_site`
- `symptom_text`
- `network_type`
- `isp_or_mobile_operator`
- `device_os`
- `vpn_client_name`
- `profile_label_without_uri`
- `direct_without_vpn_result`
- `vpn_result`
- `telegram_web_calls_media_separately`
- `other_users_affected`

## Forbidden Material

- raw VPN URI
- UUID
- private key
- bot token
- subscription link
- passwords
- provider API token
- billing data
- personal chats
- full screenshots with private data
- NL endpoint
- SPB endpoint

## Triage Groups

- `core_transport`
- `app_specific`
- `exit_ip_rejected`
- `local_client`
- `mobile_vs_fixed`
- `provider_host`

## Intake Questions

- When did the visible problem start, in local time?
- Which exact app, site, or feature fails?
- Does generic HTTPS browsing work through the VPN?
- Does the same app/site work without the VPN?
- Is the user on mobile data, home Wi-Fi, office network, or another network?
- Which ISP or mobile operator is used?
- Is the failure limited to Telegram media/calls, Telegram web/API, Russian sites, AI/dev sites, or everything?
- Are other users affected at the same time?

## Classification Hints

- one app fails while core VPN works -> app_specific_degradation
- Russian site rejects VPN but tunnel works -> exit_ip_or_vpn_rejected
- mobile fails but fixed-line works -> ISP/path-specific suspicion
- direct path works but SOCKS/VPN path fails -> vpn_path_degraded
- direct path fails but VPN works -> possible_local_isp_block
- NL transport ports fail from outside -> collect fresh read-only snapshot and provider packet

## Safe Local Steps

- Collect only the required symptom fields locally; do not paste secrets into chat.
- Run VPN_ENABLE_BLOCKING_PROBES=1 /mnt/projects/nl-diagnostics/run_vpn_incident_readonly_refresh.sh
- Compare the refreshed decision and operator-card reports.
- If only one app or service fails, keep observe and use the blocking/app policy; do not restart NL.
- Keep failover blocked unless the readiness audit explicitly allows manual probe and manual switch.

## Safe Local Commands

```bash
VPN_ENABLE_BLOCKING_PROBES=1 /mnt/projects/nl-diagnostics/run_vpn_incident_readonly_refresh.sh
sed -n '1,120p' /mnt/projects/nl-diagnostics/vpn-planning-refresh-2026-05-28.md
sed -n '1,160p' /mnt/projects/nl-diagnostics/vpn-operator-card-2026-05-28.md
```

## Blocked Actions

- Do not ask for raw VPN profile URIs, UUIDs, private keys, bot tokens, or subscription links.
- Do not restart NL for one-app or Telegram-media-only symptoms.
- Do not auto-switch profiles from symptom intake alone.
- Do not use SPB while SPB is disabled.

No NL or SPB writes were performed by this symptom intake report.
