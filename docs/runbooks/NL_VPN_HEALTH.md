# NL VPN Health Runbook

Use this runbook for the NL exit node `89.125.1.107` and the local
`singbox_tun`/v2rayN client path.

## Healthy State

- `x0tta-node.service` is active and logs `proxy=OK`.
- Local SOCKS auto-detect resolves to `127.0.0.1:10918` unless overridden.
- Current distributable Xray profile is VLESS Reality on TCP `443`.
- `/root/xray-clients` contains only active `vless-reality*.json` profiles and
  their QR files.
- Route to `89.125.1.107` bypasses `singbox_tun` through the LAN gateway.
- Generic traffic, for example `1.1.1.1`, still routes through `singbox_tun`.
- Xray validation reports primary Reality `443` reachable and marks
  `8443`, `8388`, `9443`, and `8080` as do-not-distribute until separately
  validated.
- `x0tta-vpn-watchdog.service` is active and exposes metrics on `127.0.0.1:9091`.
- `x0tta-vpn-boot-validate.timer` is enabled for post-reboot evidence.
- `x0tta-node.service` runs in observe-only mode unless an incident operator
  explicitly enables healing.

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
sudo bash /mnt/projects/x0tta6bl4-xray-vps/scripts/check-client-distribution-gate.sh
sudo bash /mnt/projects/x0tta6bl4-xray-vps/scripts/health-check.sh
sudo bash /mnt/projects/x0tta6bl4-xray-vps/scripts/validate-installation.sh
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
Client distribution gate PASS
Xray health-check HEALTHY with CLIENT DISTRIBUTION pass
Validation: primary Reality 443 reachable; fallback profiles not distributable
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

Do not distribute profiles from ports `8443`, `8388`, `9443`, or `8080` while
the validation scripts mark them as unreachable or as reaching a different TLS
service. Local listeners alone are not proof that users can connect from
outside.

For Ghost Access subscriptions, keep the public HTTP subscription edge on
`8443` if needed, but do not put `xhttp` or `ws` VPN profiles into the
subscription payload:

```bash
ssh -o BatchMode=yes -o ConnectTimeout=10 nl \
  'grep -nE "^(ENABLE_XHTTP_FALLBACK|ENABLE_GHOST_XHTTP_FALLBACK|ENABLE_GHOST_HTTPS_WS_FALLBACK|ENABLE_SECONDARY_REALITY_FALLBACK|SECONDARY_VPN_PORT)=" /opt/ghost-access-bot/shared/.env'
```

Expected:

```text
ENABLE_XHTTP_FALLBACK=0
ENABLE_GHOST_XHTTP_FALLBACK=0
ENABLE_GHOST_HTTPS_WS_FALLBACK=0
ENABLE_SECONDARY_REALITY_FALLBACK=1
SECONDARY_VPN_PORT=2083
```

Subscription payloads for active users must contain only `security=reality`
VLESS links on externally reachable Reality ports, currently `443` and optional
`2083`. Never print subscription tokens, UUIDs, raw VLESS links, or QR codes
while checking this.

The payload check also validates the client-side Reality fields that affect
anti-DPI reliability: `fingerprint` must be present and must not be `unsafe`,
and `shortId` must be empty only when explicitly allowed by the server or a
hex string with an even number of characters, up to 16 characters. A missing
or unsafe fingerprint and an invalid `shortId` are hard failures, because such
links can import successfully in some clients but fail the real Reality
handshake.

Use the deployed read-only payload check for active, non-expired users:

```bash
ssh -o BatchMode=yes -o ConnectTimeout=10 nl \
  '/opt/ghost-access-bot/shared/scripts/check_live_subscription_payload.py --limit 50 --json'
```

Expected summary shape:

```json
{
  "decision": "LIVE_SUBSCRIPTION_PAYLOAD_SAFE",
  "ok": true,
  "failures": [],
  "ports": [443, 2083],
  "transport_counts": {"reality": "<non-zero count, changes with active devices>"},
  "anti_dpi": {
    "status": "ready",
    "ready_subscription_count": "<matches checked_subscription_count>",
    "recommended_port_order": [443, 2083]
  }
}
```

`anti_dpi.status=ready` means active subscription payloads are Reality-only,
carry primary Reality `443`, carry the secondary Reality port, and do not expose
legacy transports. It also means the live sampled payloads had valid Reality
fingerprint and `shortId` shape. This is distribution readiness, not proof that
every mobile operator or ISP works. Use the combined status for the higher-level
answer:

```bash
bash scripts/vpn_status.sh --json | jq '.anti_dpi_readiness'
```

Expected after the 2026-06-05 hardening pass:

```json
{
  "distribution_ready": true,
  "all_provider_coverage_proven": false,
  "status": "attention",
  "warnings": [
    "external_provider_coverage_not_fully_verified",
    "legacy_transport_still_polling"
  ]
}
```

Do not restart `x-ui` for `anti_dpi_readiness.status=attention` when
`distribution_ready=true` and `restart_relevant_legacy=false`. That state means
the current Reality distribution is safe, but old clients or missing external
provider evidence still need follow-up.

No-progress dry-runs do not reset or extend the user-message cooldown. The
cooldown is based only on the last real `LEGACY_NO_PROGRESS_NUDGE_SENT` report.
Use `.legacy_no_progress_nudge.next_nudge_allowed_at` or
`.next_safe_action.earliest_mutation_at` for the earliest safe user-message
time; do not use the dry-run report timestamp for that decision.

Use `next_safe_action` as the final operator guard before any manual action:

```bash
bash scripts/vpn_status.sh --json | jq '.next_safe_action'
```

For a compact incident summary, use the short stable fields:

```bash
bash scripts/vpn_status.sh --json | jq '{
  overall_status,
  user_connectivity: {
    status: .user_connectivity.status,
    positive_signal_count: .user_connectivity.positive_signal_count,
    no_progress_candidate_count: .user_connectivity.no_progress_candidate_count,
    proven: .user_connectivity.user_connectivity_proven
  },
  transport_usage: {
    status: .transport_usage.status,
    severity: .transport_usage.summary.severity,
    restart_relevant: .transport_usage.summary.restart_relevant
  },
  next_safe_action: {
    action: .next_safe_action.action,
    earliest_mutation_at: .next_safe_action.earliest_mutation_at,
    user_message_allowed_after_review: .next_safe_action.user_message_allowed_after_review
  }
}'
```

Expected during partial migration: `user_connectivity.status` is
`partial_user_progress`, `user_connectivity.user_connectivity_proven=false`,
and `transport_usage.summary.restart_relevant=false`. That means keep collecting
evidence and user replies; do not restart `x-ui` for a single stale legacy
source.

If `.subscription_payload.status` is `stale` or `missing`,
`.next_safe_action.action` must be `refresh_subscription_payload_status`.
This is a read-only refresh of
`/var/lib/ghost-access/subscription-payload/latest.json`; do not treat stale
local evidence as an anti-DPI breakage and do not restart `x-ui` for it.

Expected while a no-progress nudge cooldown is active:

```json
{
  "action": "wait_for_nudge_cooldown_and_collect_readonly_evidence",
  "automatic_restart_allowed": false,
  "earliest_mutation_at": "2026-06-06T02:28:51Z",
  "earliest_mutation_seconds_until": "<seconds until cooldown ends>",
  "blocked_actions": [
    "full_server_restart",
    "restart_nl_server",
    "restart_x-ui",
    "send_duplicate_no_progress_nudge_before_cooldown"
  ]
}
```

During that state, the only immediate actions should be read-only evidence
refreshes: transport usage, migration progress, and migration replies. If those
three evidence files are fresh, `immediate_readonly_actions` may be empty; then
wait for the cooldown and refresh the deferred evidence shortly before any
user-message apply.
Use `earliest_mutation_seconds_until` for automation that needs a countdown;
do not parse only the timestamp when deciding whether a send is still blocked.
If a fresh transport usage, migration progress, migration replies, dry-run, or
subscription-payload report will expire before `earliest_mutation_at`,
`deferred_readonly_actions` must list the matching refresh action. Treat that
as a reminder to collect fresh read-only evidence shortly before apply, not as
permission to send before cooldown.
After cooldown, do not send a no-progress user nudge while
`immediate_readonly_actions` is non-empty. The expected action in that state is
`refresh_readonly_evidence_before_user_nudge`; refresh those read-only reports,
re-run `vpn_status.sh --json`, and require `immediate_readonly_actions=[]`
before any `review_and_send_no_progress_nudge` apply.

Use the local helper to refresh all required read-only NL evidence in one safe
step:

```bash
bash scripts/refresh_nl_vpn_readonly_evidence.sh
```

It starts only these oneshot collectors:
`ghost-access-transport-usage-evidence.service`,
`ghost-access-live-subscription-payload-check.service`,
`ghost-access-legacy-migration-reply-collector.service`,
`ghost-access-legacy-migration-progress.service`, and
`ghost-access-legacy-no-progress-nudge-dry-run.service`. It then downloads the
five JSON reports into `nl-diagnostics` and prints the compact status. It must
not restart `x-ui`, restart nginx, or send Telegram messages.

The no-progress dry-run timer may run during cooldown. It does not send
Telegram messages and does not require a bot token; it only writes the current
privacy-safe candidate summary:

```bash
ssh -o BatchMode=yes -o ConnectTimeout=10 nl \
  'systemctl show ghost-access-legacy-no-progress-nudge-dry-run.service ghost-access-legacy-no-progress-nudge-dry-run.timer -p Id -p ActiveState -p SubState -p Result --no-pager && jq "{decision, mode, active_user_count, progress_user_count, reply_user_count, no_progress_candidate_count, selected_user_count, sent_count, failed_count, blocked_count, privacy}" /var/lib/ghost-access/legacy-migration/no-progress-nudge-dry-run.json'
scp nl:/var/lib/ghost-access/legacy-migration/no-progress-nudge-dry-run.json \
  /mnt/projects/nl-diagnostics/nl-legacy-no-progress-nudge-dry-run-latest.json
```

Expected: `decision=LEGACY_NO_PROGRESS_NUDGE_DRY_RUN`, `mode=dry_run`,
`selected_user_count=0`, `sent_count=0`, and clean privacy flags. Use this
dry-run count for operator planning, but do not send another nudge before
`next_safe_action.earliest_mutation_at`.

`vpn_status.sh` treats the dry-run candidate summary as stale after 30 minutes
by default. If `.next_safe_action.action` becomes
`refresh_no_progress_nudge_dry_run`, run or wait for only the dry-run timer; do
not send a user nudge from stale candidate data.

Before any apply send, `.next_safe_action.no_progress_dry_run_ready_for_apply`
must be `true`. If it is `false`, refresh the dry-run report first and re-check
`next_safe_action`; do not use candidates from the previous real send report.
During cooldown, also check
`.next_safe_action.no_progress_dry_run_valid_through_earliest_mutation`. If it
is `false`, the current dry-run will expire before the earliest allowed send
time; refresh the dry-run again shortly before any apply attempt. The
`deferred_readonly_actions` field should then include
`refresh_no_progress_nudge_dry_run_before_user_nudge`.
Do the same for
`.next_safe_action.subscription_payload_valid_through_earliest_mutation`. If it
is `false`, refresh the live subscription payload status shortly before apply;
the deferred action should include
`refresh_subscription_payload_status_before_user_nudge`.

The same check is installed as a timer:

```bash
ssh -o BatchMode=yes -o ConnectTimeout=10 nl \
  'systemctl show ghost-access-live-subscription-payload-check.service ghost-access-live-subscription-payload-check.timer -p Id -p ActiveState -p SubState -p Result --no-pager'
```

Expected: service `Result=success`, timer `ActiveState=active` and
`SubState=waiting`.

The old XHTTP/WS sync timers should stay disabled after fallback delivery is
removed. Leaving the fallback services running is acceptable when avoiding a
hard disconnect for any old session, but the sync timers must not keep running
`--restart-service` every five minutes:

```bash
ssh -o BatchMode=yes -o ConnectTimeout=10 nl \
  'systemctl show ghost-access-nl-xhttp-sync.timer ghost-access-nl-https-ws-sync.timer ghost-access-nl-xhttp.service ghost-access-nl-https-ws.service -p Id -p ActiveState -p SubState --no-pager'
```

Expected: both sync timers `ActiveState=inactive`, while fallback services may
remain `active/running`.

If legacy clients are still trying `/ghost-xhttp` or `/ghost-ws`, check the
privacy-safe transport usage report. It does not store raw IPs, email, target
hosts, UUIDs, tokens, or VPN links:

```bash
ssh -o BatchMode=yes -o ConnectTimeout=10 nl \
  'systemctl start ghost-access-transport-usage-evidence.service && jq "{decision, ok, operator_action, summary, findings, windows: {\"15m\": .windows[\"15m\"].legacy_transport_health, \"60m\": .windows[\"60m\"].legacy_transport_health}}" /var/lib/ghost-access/transport-usage/latest.json'
scp nl:/var/lib/ghost-access/transport-usage/latest.json \
  /mnt/projects/nl-diagnostics/nl-transport-usage-latest.json
bash scripts/vpn_status.sh --json | jq '.transport_usage'
```

Expected for a clean legacy window: `decision=TRANSPORT_USAGE_OK`.
If it reports `TRANSPORT_USAGE_ATTENTION`, do not restart the main `x-ui`
Reality service. Treat it as a client migration or stale legacy fallback
problem. `legacy_proxy_requests_without_dataplane` means nginx saw legacy
requests but the fallback Xray access log did not record accepted user traffic
in that window. `legacy_proxy_4xx_seen` means legacy clients are receiving 4xx
responses on that path. Use `unique_proxy_source_count`,
`aggregate_unique_proxy_source_count`, `proxy_method_counts`, and
`proxy_user_agent_family_counts` to distinguish one stuck cached client from
broad client failure; these are aggregate/HMAC-safe fields and do not expose
raw IPs or raw user-agent strings.

The collector also exposes a top-level `summary` for the most recent window.
Interpret it this way:

- `severity=single_source_stale_legacy`,
  `attention_scope=single_proxy_source`,
  `aggregate_unique_proxy_source_count=1`, and `restart_relevant=false`: one
  stale/cached legacy source is still polling old paths. Do not restart `x-ui`;
  monitor migration progress and user replies.
- `severity=multi_source_legacy_attention` and `restart_relevant=false`:
  more than one legacy source is still present. Keep Reality as the only
  distributable profile and continue client migration.
- `severity=legacy_dataplane_active_with_attention`,
  `attention_scope=mixed_legacy_dataplane_and_attention`, and
  `restart_relevant=false`: at least one legacy path still has accepted
  dataplane traffic while another legacy path still has attention findings.
  This proves legacy client activity is still present; it is not a main
  Reality `x-ui` restart signal.
- `severity=legacy_proxy_server_error` and `restart_relevant=true`: legacy
  fallback proxy errors were seen. Inspect nginx/fallback upstream first; this
  still does not automatically justify restarting the main Reality `x-ui`
  service.

For the 2026-06-05 incident, the legacy signal changed over time. Earlier
post-nudge windows looked like `severity=single_source_stale_legacy`. The
later 16:18 UTC window showed accepted `/ghost-ws` dataplane plus remaining
`/ghost-xhttp` 4xx/no-dataplane attention, classified as
`severity=legacy_dataplane_active_with_attention`,
`attention_scope=mixed_legacy_dataplane_and_attention`,
`aggregate_unique_proxy_source_count=2`, and `restart_relevant=false`.
That is evidence that legacy client activity is still present and must be
migrated, not evidence that the main Reality service should be restarted.

Before touching legacy fallback services, run a dry sync. This compares the
fallback client list with `x-ui` without writing files or restarting anything:

```bash
ssh -o BatchMode=yes -o ConnectTimeout=10 nl \
  'python3 /opt/ghost-access-bot/current/scripts/sync_ghost_https_ws_clients.py --config /etc/ghost-access/nl-xhttp-8443.json --service ghost-access-nl-xhttp.service --port 10086 --path /ghost-xhttp --network xhttp --mode auto --tag ghost-https-xhttp --json'
ssh -o BatchMode=yes -o ConnectTimeout=10 nl \
  'python3 /opt/ghost-access-bot/current/scripts/sync_ghost_https_ws_clients.py --config /etc/ghost-access/nl-https-ws-8443.json --service ghost-access-nl-https-ws.service --port 10085 --path /ghost-ws --network ws --mode auto --tag ghost-https-ws --json'
```

If `changed=true` and many users are still on cached legacy profiles, back up
the two configs and apply only the scoped fallback sync. This may briefly
restart `ghost-access-nl-xhttp.service` and `ghost-access-nl-https-ws.service`,
but must not restart `x-ui.service` or the main Reality inbounds:

```bash
ssh -o BatchMode=yes -o ConnectTimeout=10 nl '
set -euo pipefail
stamp=$(date -u +%Y%m%dT%H%M%SZ)
cp /etc/ghost-access/nl-xhttp-8443.json /etc/ghost-access/nl-xhttp-8443.json.bak-sync-legacy-${stamp}
cp /etc/ghost-access/nl-https-ws-8443.json /etc/ghost-access/nl-https-ws-8443.json.bak-sync-legacy-${stamp}
python3 /opt/ghost-access-bot/current/scripts/sync_ghost_https_ws_clients.py --config /etc/ghost-access/nl-xhttp-8443.json --service ghost-access-nl-xhttp.service --port 10086 --path /ghost-xhttp --network xhttp --mode auto --tag ghost-https-xhttp --apply --restart-service --json
python3 /opt/ghost-access-bot/current/scripts/sync_ghost_https_ws_clients.py --config /etc/ghost-access/nl-https-ws-8443.json --service ghost-access-nl-https-ws.service --port 10085 --path /ghost-ws --network ws --mode auto --tag ghost-https-ws --apply --restart-service --json
systemctl show x-ui.service ghost-access-nl-xhttp.service ghost-access-nl-https-ws.service -p Id -p ActiveState -p SubState -p MainPID -p NRestarts --no-pager
'
```

After the scoped sync, dry sync should return `changed=false`, active
subscription payloads must still be Reality-only, and `vpn_status.sh --json`
may remain `advisory` until old clients either produce fallback dataplane
events or migrate to the current Reality subscription.

Build the privacy-safe migration packet before asking users to refresh cached
legacy profiles:

```bash
ssh -o BatchMode=yes -o ConnectTimeout=10 nl '
python3 /opt/ghost-access-bot/current/scripts/build_legacy_client_migration_packet.py \
  --transport-usage /var/lib/ghost-access/transport-usage/latest.json \
  --subscription-payload /var/lib/ghost-access/subscription-payload/latest.json \
  --db-path /opt/ghost-access-bot/shared/x0tta6bl4.db \
  --json-out /var/lib/ghost-access/legacy-migration/latest.json \
  --markdown-out /var/lib/ghost-access/legacy-migration/latest.md \
  --write --json
'
scp nl:/var/lib/ghost-access/legacy-migration/latest.json \
  /mnt/projects/nl-diagnostics/nl-legacy-client-migration-packet-2026-06-05.json
bash scripts/vpn_status.sh --json | jq '.legacy_migration'
```

Expected: `decision=LEGACY_CLIENT_MIGRATION_PACKET_READY`,
`automatic_broadcast_allowed=false`, and `privacy_ok=true`. The packet message
asks users to open the bot, press `Подключить`, import the fresh Reality
profile, and remove old Ghost Access `xhttp`, `ws`, or `8443` profiles. It does
not include subscription links, profile links, UUIDs, IPs, chat IDs, or user IDs.

Before sending the migration message, run the sender in dry-run mode. Dry-run
does not send Telegram messages and prints aggregate counts only:

```bash
ssh -o BatchMode=yes -o ConnectTimeout=10 nl '
python3 /opt/ghost-access-bot/current/scripts/send_legacy_client_migration_message.py \
  --packet /var/lib/ghost-access/legacy-migration/latest.json \
  --db-path /opt/ghost-access-bot/shared/x0tta6bl4.db \
  --json
'
```

Expected: `mode=dry_run`, `candidate_active_user_count` matches the active
legacy migration audience, `selected_user_count=0`, `sent_count=0`,
`failed_count=0`, and all privacy flags are `false`.

Send only after the operator has reviewed the packet and decided that the
message text is correct. The sender requires an explicit SHA-256 packet binding,
confirmation text, positive limit, and Telegram bot token from the local NL
environment. It still prints only aggregate counts:

```bash
packet_sha=$(ssh -o BatchMode=yes -o ConnectTimeout=10 nl \
  "sha256sum /var/lib/ghost-access/legacy-migration/latest.json | awk '{print \$1}'")
ssh -o BatchMode=yes -o ConnectTimeout=10 nl "
python3 /opt/ghost-access-bot/current/scripts/send_legacy_client_migration_message.py \
  --packet /var/lib/ghost-access/legacy-migration/latest.json \
  --db-path /opt/ghost-access-bot/shared/x0tta6bl4.db \
  --apply \
  --confirm SEND_LEGACY_MIGRATION \
  --expect-packet-sha256 $packet_sha \
  --limit 14 \
  --json
"
```

Do not run the apply command when the migration packet, dry-run result, or
operator audience size is stale. Rebuild the packet and re-run dry-run first.

After the message is sent, keep the reply collector active. It reads
`telegram-bot-simple.service` journal, accepts only the four short replies, and
writes a sanitized aggregate summary. It must not store raw user IDs, chat IDs,
subscription tokens, VPN links, UUIDs, IPs, Telegram handles, screenshots, or
logs:

```bash
ssh -o BatchMode=yes -o ConnectTimeout=10 nl '
systemctl show ghost-access-legacy-migration-reply-collector.service \
  ghost-access-legacy-migration-reply-collector.timer \
  -p Id -p ActiveState -p SubState -p Result --no-pager
python3 /opt/ghost-access-bot/current/scripts/collect_legacy_migration_replies_from_bot_journal.py \
  --packet /var/lib/ghost-access/legacy-migration/latest.json \
  --json-out /var/lib/ghost-access/legacy-migration/replies.json \
  --markdown-out /var/lib/ghost-access/legacy-migration/replies.md \
  --confirm-current-packet COLLECT_CURRENT_LEGACY_REPLIES \
  --write --json
'
scp nl:/var/lib/ghost-access/legacy-migration/replies.json \
  /mnt/projects/nl-diagnostics/nl-legacy-client-migration-replies-2026-06-05.json
bash scripts/vpn_status.sh --json | jq '.legacy_migration_replies'
```

Expected before users answer: `status=no_client_replies`, `total_replies=0`,
and `privacy_ok=true`. Expected after at least one successful user reply:
`status=partial_client_replies`, `done_updated_count>0`, and `privacy_ok=true`.

Also keep the migration progress collector active. Replies are useful, but they
are not the only real signal. Progress also counts human subscription refreshes,
`config` requests, and Reality device activity after the migration message. It
excludes technical probes such as `x0tta-live-subscription-payload-check`, curl,
local loopback probes, canaries, monitoring agents, and generic HTTP clients:

```bash
ssh -o BatchMode=yes -o ConnectTimeout=10 nl '
systemctl show ghost-access-legacy-migration-progress.service \
  ghost-access-legacy-migration-progress.timer \
  -p Id -p ActiveState -p SubState -p Result --no-pager
python3 /opt/ghost-access-bot/current/scripts/collect_legacy_migration_progress.py \
  --packet /var/lib/ghost-access/legacy-migration/latest.json \
  --message-send /var/lib/ghost-access/legacy-migration/message-send.json \
  --replies /var/lib/ghost-access/legacy-migration/replies.json \
  --db-path /opt/ghost-access-bot/shared/x0tta6bl4.db \
  --json-out /var/lib/ghost-access/legacy-migration/progress.json \
  --markdown-out /var/lib/ghost-access/legacy-migration/progress.md \
  --confirm-current-progress COLLECT_CURRENT_LEGACY_PROGRESS \
  --write --json
'
scp nl:/var/lib/ghost-access/legacy-migration/progress.json \
  /mnt/projects/nl-diagnostics/nl-legacy-client-migration-progress-2026-06-05.json
bash scripts/vpn_status.sh --json | jq '.legacy_migration_progress'
```

Expected after the 2026-06-05 migration send: `message_send.sent_count=14`,
`privacy_ok=true`, and no technical canary user agents counted as human
subscription progress. A healthy partial rollout can show
`status=migration_progress_seen` while `legacy_migration_replies` is still
`no_client_replies`; that means some clients are using fresh Reality activity
but have not sent a short confirmation yet.

If legacy transport still shows recent proxy requests and some active users
have no progress after the first migration message, use the no-progress nudge
sender. It is dry-run-first, excludes users who already showed Reality device
activity, human subscription pulls, or short replies, and enforces min-age plus
cooldown checks:

```bash
ssh -o BatchMode=yes -o ConnectTimeout=10 nl '
python3 /opt/ghost-access-bot/current/scripts/send_legacy_no_progress_nudge.py \
  --packet /var/lib/ghost-access/legacy-migration/latest.json \
  --message-send /var/lib/ghost-access/legacy-migration/message-send.json \
  --replies /var/lib/ghost-access/legacy-migration/replies.json \
  --db-path /opt/ghost-access-bot/shared/x0tta6bl4.db \
  --json-out /var/lib/ghost-access/legacy-migration/no-progress-nudge-dry-run.json \
  --min-age-minutes 30 \
  --write \
  --json
'
```

Expected dry-run after the 2026-06-05 send: aggregate counts only, with
`mode=dry_run`, `selected_user_count=0`, and all privacy flags `false`.

Apply only after reviewing the dry-run counts, current legacy transport
attention, and cooldown. The apply command must bind to the current migration
packet hash, reviewed dry-run report hash, live subscription payload hash,
transport usage hash, and replies hash:

The sender always checks the canonical last-send report
`/var/lib/ghost-access/legacy-migration/no-progress-nudge.json` for cooldown,
even if `--json-out` is changed. Do not change `--json-out` in normal
operations; a custom output path is for diagnostics only and must not be used
to bypass cooldown.

Before the apply command, run the local review guard:

```bash
bash scripts/review_nl_no_progress_nudge.sh
```

It first runs `refresh_nl_vpn_readonly_evidence.sh`, then checks
`next_safe_action`. Continue to the apply command only when the review JSON
reports `ready=true`, `action=review_and_send_no_progress_nudge`,
`user_message_allowed_after_review=true`, `immediate_readonly_actions=[]`, and
`transport_restart_relevant=false`. During cooldown it must report
`ready=false`, `cooldown_active=true`, `reason=no-progress nudge cooldown is
active`, `ready_blockers` containing `cooldown_active`, the same
`earliest_mutation_at` as `vpn_status.sh`, and a positive
`earliest_mutation_seconds_until`. When `ready=false`, use `ready_blockers` as
the first explanation of why sending is still blocked.
The same JSON is saved to
`nl-diagnostics/nl-no-progress-nudge-review-latest.json` for audit.
If the post-review hash collection fails after `ready=true`, the review file
must report `ready=false`, `hash_collection_status=failed`, and the
`hash_collection_exit_code`; do not proceed to send. The failure audit stores
only the error output size and SHA-256, not the raw error body.

Prefer the guarded local sender over hand-copying the apply command. It runs the
review guard first, refuses when `ready=false` or `ready_blockers` is not
empty, independently re-checks the review invariants, requires
`CONFIRM_NL_NO_PROGRESS_NUDGE=SEND_NL_NO_PROGRESS_NUDGE`, binds all five
expected hashes, and stores the aggregate send report locally:

```bash
CONFIRM_NL_NO_PROGRESS_NUDGE=SEND_NL_NO_PROGRESS_NUDGE \
  bash scripts/send_nl_no_progress_nudge_guarded.sh
```

Expected during cooldown: `applied=false`, `status=blocked_by_review_guard`,
and no Telegram messages sent. Continue only after the review block reports
`ready=true`, `ready_blockers=[]`, `action=review_and_send_no_progress_nudge`,
`user_message_allowed_after_review=true`, `cooldown_active=false`,
`transport_restart_relevant=false`, `hash_collection_status=success`,
`hash_collection_exit_code=0`, and `immediate_readonly_actions=[]`.
The guarded sender writes its own audit result to
`nl-diagnostics/nl-no-progress-nudge-guarded-send-latest.json` whether it
sends, refuses, the review guard fails, the review guard returns invalid JSON,
the remote sender fails, or the remote sender returns invalid JSON. For invalid
review or sender output, the audit stores only output size and SHA-256, not the
raw output body.
Do not override `REVIEW_CMD` or `SSH_CMD` during operations; those overrides
exist only for local tests of the guard behavior.

```bash
packet_sha=$(ssh -o BatchMode=yes -o ConnectTimeout=10 nl \
  "sha256sum /var/lib/ghost-access/legacy-migration/latest.json | awk '{print \$1}'")
dry_run_sha=$(ssh -o BatchMode=yes -o ConnectTimeout=10 nl \
  "sha256sum /var/lib/ghost-access/legacy-migration/no-progress-nudge-dry-run.json | awk '{print \$1}'")
subscription_payload_sha=$(ssh -o BatchMode=yes -o ConnectTimeout=10 nl \
  "sha256sum /var/lib/ghost-access/subscription-payload/latest.json | awk '{print \$1}'")
transport_usage_sha=$(ssh -o BatchMode=yes -o ConnectTimeout=10 nl \
  "sha256sum /var/lib/ghost-access/transport-usage/latest.json | awk '{print \$1}'")
replies_sha=$(ssh -o BatchMode=yes -o ConnectTimeout=10 nl \
  "sha256sum /var/lib/ghost-access/legacy-migration/replies.json | awk '{print \$1}'")
ssh -o BatchMode=yes -o ConnectTimeout=10 nl "
set -a
. /opt/ghost-access-bot/shared/.env
set +a
python3 /opt/ghost-access-bot/current/scripts/send_legacy_no_progress_nudge.py \
  --packet /var/lib/ghost-access/legacy-migration/latest.json \
  --message-send /var/lib/ghost-access/legacy-migration/message-send.json \
  --replies /var/lib/ghost-access/legacy-migration/replies.json \
  --db-path /opt/ghost-access-bot/shared/x0tta6bl4.db \
  --json-out /var/lib/ghost-access/legacy-migration/no-progress-nudge.json \
  --dry-run-report /var/lib/ghost-access/legacy-migration/no-progress-nudge-dry-run.json \
  --subscription-payload-status /var/lib/ghost-access/subscription-payload/latest.json \
  --transport-usage-status /var/lib/ghost-access/transport-usage/latest.json \
  --min-age-minutes 30 \
  --cooldown-hours 12 \
  --dry-run-max-age-minutes 30 \
  --subscription-payload-max-age-minutes 30 \
  --transport-usage-max-age-minutes 15 \
  --replies-max-age-minutes 30 \
  --apply \
  --confirm SEND_LEGACY_NO_PROGRESS_NUDGE \
  --expect-packet-sha256 $packet_sha \
  --expect-dry-run-sha256 $dry_run_sha \
  --expect-subscription-payload-sha256 $subscription_payload_sha \
  --expect-transport-usage-sha256 $transport_usage_sha \
  --expect-replies-sha256 $replies_sha \
  --limit <dry-run-no-progress-candidate-count> \
  --json
"
scp nl:/var/lib/ghost-access/legacy-migration/no-progress-nudge.json \
  /mnt/projects/nl-diagnostics/nl-legacy-no-progress-nudge-2026-06-05.json
```

For the 2026-06-05 incident, the first no-progress nudge sent to 7 candidates
with `sent_count=7`, `failed_count=0`, `blocked_count=0`, and all privacy flags
`false`.

The local status JSON exposes the nudge and cooldown state:

```bash
bash scripts/vpn_status.sh --json | jq '.legacy_no_progress_nudge'
```

Expected after the first 2026-06-05 no-progress nudge:
`status=sent`, `sent_count=7`, `cooldown_active=true`, `privacy_ok=true`, and
`next_nudge_allowed_at=2026-06-06T02:28:51Z`.

Record only short migration replies. First validate without writing:

```bash
packet_sha=$(sha256sum /mnt/projects/nl-diagnostics/nl-legacy-client-migration-packet-2026-06-05.json | awk '{print $1}')
printf '%s\n' 'done updated' | \
  python3 services/nl-server/ghost-access/record_legacy_client_migration_reply.py \
    --packet /mnt/projects/nl-diagnostics/nl-legacy-client-migration-packet-2026-06-05.json \
    --reporter-label legacy-client-1 \
    --reply-stdin \
    --expect-packet-sha256 "$packet_sha" \
    --json
```

Then write only after operator review:

```bash
printf '%s\n' 'done updated' | \
  python3 services/nl-server/ghost-access/record_legacy_client_migration_reply.py \
    --packet /mnt/projects/nl-diagnostics/nl-legacy-client-migration-packet-2026-06-05.json \
    --reporter-label legacy-client-1 \
    --reply-stdin \
    --expect-packet-sha256 "$packet_sha" \
    --write --json
```

Allowed replies are exactly `done updated`, `fail import`, `fail timeout`, and
`fail no-internet`. Do not store raw links, QR codes, UUIDs, IPs, screenshots,
logs, usernames, Telegram handles, phone numbers, user IDs, or chat IDs.

The local VPN status JSON also reads the latest sanitized payload snapshot when
`/mnt/projects/nl-diagnostics/nl-live-subscription-payload-latest.json` exists:

```bash
bash scripts/vpn_status.sh --json | jq '.subscription_payload'
```

Expected: `status=safe`, `fresh=true`, `ports=[443,2083]`,
`transport_counts.reality` non-zero, and `failures=[]`.

Expired, missing, rate-limited, or no-device subscription requests must not
return fake VLESS profiles. They should return real HTTP error responses such
as `403`, `404`, `409`, or `429` with plain text. A quick aggregate check for
expired tokens should show `max_profile_count=0` and no ports.

The same status JSON exposes the user-connectivity verification gate:

```bash
bash scripts/vpn_status.sh --json | jq '.user_connectivity_verification'
```

Interpretation:

- `user_connectivity_proven=true`: every active target user has confirmed with
  a short allowed reply and no failure replies were recorded.
- `status=partial_user_progress`: some users have real signals, such as fresh
  Reality device activity or human subscription refreshes, but the rollout is
  not fully proven.
- `unconfirmed_by_reply_count`: active target users who have not sent a
  positive short reply.
- `unverified_by_any_signal_count`: active target users with no reply, no
  human subscription refresh, and no Reality device activity after the
  migration message.
- `operator_action=wait_for_replies_and_monitor_until_nudge_cooldown`: do not
  send another message until `next_nudge_allowed_at`; keep monitoring replies,
  progress, and legacy transport.
- `legacy_transport_still_polling` in `blockers`: old client traffic is still
  present. It can be stale polling or active legacy dataplane; inspect
  `.transport_usage.severity` before deciding what it means.

For the 2026-06-05 incident, the gate is expected to remain
`user_connectivity_proven=false` until real users answer. Server health,
Reality-only subscriptions, and port 443 reachability are necessary evidence,
but they do not by themselves prove that every user has fixed their client.

Confirm the observe-only safety flags before using `x0tta-node.service` as
evidence:

```bash
systemctl cat x0tta-node.service | sed -n '1,160p'
pid=$(systemctl show -p MainPID --value x0tta-node.service)
sudo tr '\0' '\n' < /proc/$pid/environ | grep -E 'VPN_SELF_HEAL_ENABLE|VPN_ENABLE_REALITY_ROTATION|VPN_ENABLE_PULSE_SHIFT|PYTHONPATH|X0TTA6BL4_EVENT_PROJECT_ROOT'
```

Expected:

```text
VPN_SELF_HEAL_ENABLE=false
VPN_ENABLE_REALITY_ROTATION=false
VPN_ENABLE_PULSE_SHIFT=false
PYTHONPATH=/mnt/projects
X0TTA6BL4_EVENT_PROJECT_ROOT=/mnt/projects
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
snapshot_count=11
trend=stable_no_probe_evidence
latest_snapshot=20260528T034120Z
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
blocking_history_snapshot_count=11
manual_failover_status=planning_not_active
manual_failover_readiness_status=blocked_no_incident_trigger
manual_failover_probe_allowed=False
manual_failover_switch_allowed=False
secondary_candidate_score_status=missing_candidates
secondary_candidate_viable_count=0
secondary_exit_requirements_status=requirements_ready_no_candidate
secondary_exit_requirements_missing=NET-01
secondary_provider_shortlist_status=shortlist_ready_no_endpoint
secondary_provider_shortlist_count=5
secondary_provider_shortlist_endpoint_count=0
secondary_candidate_intake_status=awaiting_public_candidate_metadata
secondary_candidate_intake_allowed_fields=7
secondary_provisioning_plan_status=provisioning_plan_ready_no_endpoint
secondary_provisioning_external_action_required=True
secondary_provisioning_endpoint_count=0
secondary_exit_flow_status=blocked_missing_candidate
secondary_exit_flow_candidate_configured=False
secondary_exit_flow_manual_switch_allowed=False
secondary_manual_drill_status=drill_plan_ready_blocked_no_endpoint
secondary_manual_drill_test_scope=single_client
secondary_manual_drill_rollback_required=True
secondary_selection_packet_status=selection_packet_ready_no_endpoint
secondary_selection_recommended_label=upcloud-fi-hel
secondary_selection_backup_label=ovhcloud-pl-waw
secondary_selection_option_count=3
secondary_selection_may_create_endpoint_now=False
secondary_public_metadata_template_status=public_metadata_template_ready_no_endpoint
secondary_public_metadata_selected_label=upcloud-fi-hel
secondary_public_metadata_candidate_file_update_allowed=False
secondary_post_provision_validation_status=post_provision_validation_ready_waiting_endpoint
secondary_post_provision_can_generate_probe_config=False
secondary_post_provision_can_run_public_probe=False
secondary_post_provision_test_client_allowed=False
local_diagnostic_environment_status=watch_root_full_tmpdir_available
local_root_status=critical_full
local_tmpdir_writable=True
local_recommended_tmpdir_prefix=TMPDIR=/mnt/projects/.tmp
local_root_cleanup_plan_status=manual_cleanup_plan_ready
local_root_cleanup_estimated_reclaim_gib=3.24
local_root_cleanup_execute_allowed=False
local_root_cleanup_approval_packet_status=cleanup_approval_packet_ready
local_root_cleanup_approval_required=True
local_root_cleanup_commands_executed=0
incident_symptom_intake_status=symptom_intake_ready_observe
incident_symptom_required_fields=12
incident_symptom_forbidden_material=12
nl_transport_probe_status=healthy
nl_transport_probe_ok_count=3/3
nl_transport_uptime_status=stable_healthy
nl_transport_uptime_samples=24
nl_transport_uptime_bad_streak=0
secondary_probe_template_status=planning_template
readiness_audit_status=ready_local_with_future_blocks
readiness_missing=0
incident_timeline_event_count=22
incident_timeline_latest_type=provider_watch
incident_timeline_latest_snapshot=20260528T034120Z
nl_mutation_allowed=false
spb_fallback_allowed=false
```

Readiness audit:

```text
nl-diagnostics/vpn-plan-readiness-audit-2026-05-28.md
```

Current audit summary:

```text
ready_local=24
blocked_future_approval=4
watch=3
missing=0
watch_items=BOOT-01, LOCALENV-01, LOCALCLEAN-01
blocked_items=FAILOVER-03, FAILOVER-06, GATE-01, FAILOVER-02
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

Local root cleanup plan:

```text
nl-diagnostics/local-root-cleanup-plan-2026-05-28.md
nl-diagnostics/local-root-cleanup-approval-packet-2026-05-28.md
```

Current rule:

```text
status=manual_cleanup_plan_ready
estimated_reclaim_gib=3.24
cleanup_execute_allowed=false
approval_packet_status=cleanup_approval_packet_ready
approval_required=true
commands_executed=0
```

Interpretation: this is a review plan only. It does not delete files and all
command previews require separate local cleanup approval before execution.

Outside-in NL transport probe:

```text
nl-diagnostics/nl-transport-probe-2026-05-28.md
```

Current result:

```text
89.125.1.107:443 ok
production_distributable_profile=reality:443
historical auxiliary ports are not current distribution evidence
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
sample_count=24
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
transport_status=advisory
recommended_action=observe provider signal; do not restart NL while transport is healthy/advisory
```

Provider packet for the same snapshot:

```text
nl-diagnostics/provider-incident-packets/provider-incident-packet-20260528T034120Z.md
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
event_count=22
latest_event_type=provider_watch
latest_snapshot=20260528T034120Z
```

Freshness rule:

```text
snapshot_age_seconds <= 3600 -> fresh evidence
snapshot_age_seconds > 3600 -> collect a new read-only snapshot before action
```

For the shortest incident checklist, open:

```text
nl-diagnostics/vpn-operator-card-2026-05-28.md
nl-diagnostics/vpn-incident-symptom-intake-2026-05-28.md
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
nl-diagnostics/secondary-exit-provider-shortlist-2026-05-28.md
nl-diagnostics/secondary-exit-provisioning-plan-2026-05-28.md
nl-diagnostics/secondary-exit-flow-2026-05-28.md
nl-diagnostics/secondary-exit-manual-drill-2026-05-28.md
nl-diagnostics/secondary-exit-selection-packet-2026-05-28.md
nl-diagnostics/secondary-exit-public-metadata-template-2026-05-28.md
nl-diagnostics/secondary-exit-post-provision-validation-2026-05-28.md
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
secondary_provider_shortlist_status=shortlist_ready_no_endpoint
secondary_provider_shortlist_count=5
secondary_provider_shortlist_endpoint_count=0
secondary_candidate_intake_status=awaiting_public_candidate_metadata
secondary_candidate_intake_allowed_fields=7
secondary_provisioning_plan_status=provisioning_plan_ready_no_endpoint
secondary_provisioning_external_action_required=true
secondary_provisioning_endpoint_count=0
secondary_exit_flow_status=blocked_missing_candidate
secondary_exit_flow_candidate_configured=false
secondary_exit_flow_manual_switch_allowed=false
secondary_manual_drill_status=drill_plan_ready_blocked_no_endpoint
secondary_manual_drill_test_scope=single_client
secondary_manual_drill_rollback_required=true
secondary_selection_packet_status=selection_packet_ready_no_endpoint
secondary_selection_recommended_label=upcloud-fi-hel
secondary_selection_backup_label=ovhcloud-pl-waw
secondary_selection_option_count=3
secondary_selection_may_create_endpoint_now=false
secondary_public_metadata_template_status=public_metadata_template_ready_no_endpoint
secondary_public_metadata_selected_label=upcloud-fi-hel
secondary_public_metadata_candidate_file_update_allowed=false
secondary_post_provision_validation_status=post_provision_validation_ready_waiting_endpoint
secondary_post_provision_can_generate_probe_config=false
secondary_post_provision_can_run_public_probe=false
secondary_post_provision_test_client_allowed=false
automatic_failover_allowed=false
spb_fallback_allowed=false
secondary exit node must be new provider/region, not NL and not SPB
```

Secondary exit flow:

```text
provider_shortlist_report=nl-diagnostics/secondary-exit-provider-shortlist-2026-05-28.md
provisioning_plan_report=nl-diagnostics/secondary-exit-provisioning-plan-2026-05-28.md
intake_report=nl-diagnostics/secondary-exit-candidate-intake-2026-05-28.md
manual_drill_report=nl-diagnostics/secondary-exit-manual-drill-2026-05-28.md
selection_packet_report=nl-diagnostics/secondary-exit-selection-packet-2026-05-28.md
public_metadata_template_report=nl-diagnostics/secondary-exit-public-metadata-template-2026-05-28.md
post_provision_validation_report=nl-diagnostics/secondary-exit-post-provision-validation-2026-05-28.md
status=blocked_missing_candidate
post_provision_status=post_provision_validation_ready_waiting_endpoint
selection=primary upcloud-fi-hel, backup ovhcloud-pl-waw, fallback review hetzner-de-or-fi
validation=score metadata -> generate probe config -> run public probe -> test client gate -> manual switch gate
phases=CANDIDATE-01 blocked, CONFIG-01 blocked, PROBE-01 blocked, CLIENT-01 blocked, SWITCH-01 blocked
safe_config_command=create_secondary_exit_config.py -> /mnt/projects/.tmp/secondary-exit-probe.json
safe_probe_command=probe_secondary_exit.py --config /mnt/projects/.tmp/secondary-exit-probe.json
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
infra/systemd/x0tta-node-safe-observe.conf
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
ssh -o BatchMode=yes -o ConnectTimeout=10 nl 'ss -lntup | egrep ":(443|2083|2443|4433|4434|51820|62789)" || true'
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
