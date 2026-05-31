# NL Ghost Access Source Candidates

Priority source candidates from NL:

```text
run_vpn_delivery_canary.py
run_vpn_service_access_agent.py
sync_spb_standalone_clients.py
sync_xray_device_activity.py
xray_runtime_user_manager.py
xui_client_manager.py
```

These scripts connect Ghost Access, canary checks, x-ui runtime user state, and
subscription/access health.

Some older local backup copies exist, but gap-analysis shows their hashes mostly
differ from current NL. Treat backups as history, not source of truth.

Reviewed source now copied here:

```text
check_bot_user_chains.py
run_vpn_delivery_canary.py
run_vpn_service_access_agent.py
sync_spb_standalone_clients.py
sync_xray_device_activity.py
xray_runtime_user_manager.py
xui_client_manager.py
```

`sync_xray_device_activity.py` matches the current NL source hash and has local
tests for access-log parsing, x-ui helper parsing, state cursor behavior and
missing-log handling. It is still not deployable to NL while NL is read-only.

The canary, service-access agent, runtime user manager, and x-ui client manager
also match current NL hashes. They are class C review-only sources because they
can read production databases, alter runtime Xray users, or modify x-ui client
state. Do not run them locally or deploy them to NL without an explicit mutation
gate.

`sync_spb_standalone_clients.py` also matches the current NL source hash, but SPB
is currently disabled and not used. Treat this as inactive class C review-only
source: at runtime it reads active UUIDs from NL, writes a remote SPB Xray
config, and restarts remote `xray`. Keep it non-deployable and do not use it for
VPN recovery while SPB remains offline.

## Subscription 404 Recovery

If a VPN client shows `Подписка не найдена (HTTP 404)` for a Ghost Access
subscription, the `/sub/{token}` route reached the bot server but did not find
that token in either `users.subscription_token` or
`offline_subscriptions.subscription_token`.

Do not paste subscription URLs or tokens into chat. Run the diagnostic directly
on the server that has the bot SQLite database, from this repository checkout:

```bash
cd /path/to/x0tta6bl4
python3 services/nl-server/ghost-access/diagnose_subscription_404.py \
  --db-path /opt/ghost-access-bot/shared/x0tta6bl4.db \
  --subscription-url 'https://example.invalid/sub/PASTE_TOKEN_LOCALLY' \
  --json
```

For an offline subscription visible in the client as
`Ghost Access-Offline-ABC123`, use the suffix or full claim code locally:

```bash
cd /path/to/x0tta6bl4
SUBSCRIPTION_BASE_URL='https://89-125-1-107.sslip.io:8443' \
python3 services/nl-server/ghost-access/diagnose_subscription_404.py \
  --db-path /opt/ghost-access-bot/shared/x0tta6bl4.db \
  --claim-code ABC123 \
  --repair-offline-token
```

For the screenshot-style case where the app truncates the label, for example
`Ghost Access-Offline-JWU8V...`, use the visible suffix. The command repairs only
when exactly one row matches:

```bash
cd /path/to/x0tta6bl4
SUBSCRIPTION_BASE_URL='https://89-125-1-107.sslip.io:8443' \
python3 services/nl-server/ghost-access/diagnose_subscription_404.py \
  --db-path /opt/ghost-access-bot/shared/x0tta6bl4.db \
  --label-like JWU8V \
  --repair-offline-token
```

The command prints a local `subscription_url`. Send that URL to the user through
the normal private support channel and ask them to re-import the subscription in
the VPN app. Add `--rotate` only when the old token must be invalidated.
