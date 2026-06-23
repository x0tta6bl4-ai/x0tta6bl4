# NL Anti-Block Rollout - 2026-06-01

## Status

`IMPLEMENTED_CANARY`

NL now has user-delivered fallback transports that are not the previous raw
Reality TCP path:

- primary legacy path: `VLESS Reality TCP` on `443`
- secondary legacy public ports still alive: `2083`, `39829`
- fallback path: `VLESS over TLS XHTTP` on nginx `8443`, path `/ghost-xhttp`
- fallback path: `VLESS over TLS WebSocket` on nginx `8443`, path `/ghost-ws`
- local backend: standalone Xray on `127.0.0.1:10085`
- local XHTTP backend: standalone Xray on `127.0.0.1:10086`

The current deployment keeps existing `x-ui` and `443` sessions untouched.

## Runtime Evidence

Checked on NL after rollout:

- `x-ui`: active
- `nginx`: active
- `telegram-bot-simple.service`: active
- `ghost-access-nl-https-ws.service`: active
- `ghost-access-nl-https-ws-sync.timer`: active
- public WebSocket upgrade: `HTTP/1.1 101 Switching Protocols`
- public XHTTP dataplane: temporary Xray client via nginx `8443` succeeded
- subscription payload: includes `8443` TLS XHTTP, `8443` TLS WebSocket,
  `2083` Reality TCP, and `443` Reality TCP
- temporary Xray client via subscription `8443` XHTTP profile: `dataplane_ok=true`
- temporary Xray client via subscription `8443` profile: `dataplane_ok=true`
- runtime-state:
  - `public_ingress_ports=[443,2083,39829]`
  - `ghost_xhttp_service_ok=true`
  - `ghost_xhttp_backend_ready=true`
  - `ghost_xhttp_public_port_ready=true`
  - `ghost_xhttp_path_status=404`
  - `ghost_xhttp_ready=true`
  - `ghost_https_ws_service_ok=true`
  - `ghost_https_ws_backend_ready=true`
  - `ghost_https_ws_public_port_ready=true`
  - `ghost_https_ws_upgrade_ok=true`
  - `ghost_https_ws_ready=true`
- transport usage evidence:
  - source: `/var/lib/ghost-access/transport-usage/latest.json`
  - `raw_identifiers_stored=false`
  - `raw_email_stored=false`
  - `raw_ip_stored=false`
  - `raw_target_host_stored=false`
  - `client_hashes_hmac_keyed=true`
  - latest observed 60m window on rollout: XHTTP dataplane events present,
    WebSocket dataplane events present
- runtime operator summary:
  - source: `/opt/x0tta6bl4-mesh/state/runtime-state.json`
  - field: `hot_path_summary.transport_usage_60m`
  - checked at `2026-06-01T21:07:50Z`
  - `privacy_ok=true`
  - `ghost_xhttp_dataplane_events=2`
  - `ghost_xhttp_nginx_requests=21`
  - `ghost_https_ws_dataplane_events=77`
  - `ghost_https_ws_nginx_requests=121`
- read-only diagnostics:
  - `nl-diagnostics/collect_vpn_readonly_snapshot.sh` now includes named
    XHTTP/WS service states and `transport_usage_60m`
  - `nl-diagnostics/collect_nl_server_profile_readonly.sh` now includes
    XHTTP/WS unit definitions, fallback config hashes, and `transport_usage_60m`
  - checked snapshots:
    `/tmp/x0tta-nl-snapshots/20260601T210808Z`,
    `/tmp/x0tta-nl-server-profile/20260601T210907Z`
- operator API:
  - source: `http://127.0.0.1:9472/transport-usage`
  - `/health` now includes `ghost_xhttp_ready`, `ghost_https_ws_ready`,
    `transport_usage_ok`, and `transport_usage_60m`
  - `/transport-usage` returns only aggregate readiness and 60m usage summary
  - checked privacy: no `client_hashes_sample`, email, raw IP, raw target host,
    or VPN URI in `/transport-usage`
- operator bot:
  - admin command: `/anti_block`
  - admin menu button: `Anti-block`
  - source: local status API `/transport-usage`
  - output includes XHTTP/WS readiness, subscription status, 60m dataplane/nginx
    counts, unique client counts, runtime timestamp, and usage timestamp
  - output is aggregate-only: no raw IP, email, UUID, VPN URI, or client hash
    samples
  - `/anti_block` also includes rollback dry-run status from
    `/opt/ghost-access-bot/current/scripts/rollback_ghost_fallbacks.py --json`
  - rollback section confirms current/target fallback flags, safety checks, and
    required confirmation tokens without applying rollback
- rollback tool:
  - source: `/opt/ghost-access-bot/current/scripts/rollback_ghost_fallbacks.py`
  - default mode: `delivery-only`
  - default run is dry-run/read-only
  - `delivery-only` rollback disables future Ghost fallback delivery in bot env
    but keeps fallback services running, so current XHTTP/WS sessions are not
    intentionally dropped
  - real apply requires `--apply --confirm ROLLBACK_GHOST_FALLBACKS`
  - service-stop/full rollback additionally requires
    `--service-stop-confirm STOP_GHOST_FALLBACK_SERVICES`
  - checked on NL: dry-run ok, apply without confirm returns
    `ROLLBACK_BLOCKED`, env flags stayed enabled, services stayed active
- rollback drill:
  - checked on NL at `2026-06-01T21:58:15Z..21:58:20Z`
  - delivery-only rollback applied with explicit confirmation:
    `ROLLBACK_APPLIED`, `ok=true`
  - fallback delivery flags changed `1 -> 0 -> 1`
  - after rollback and after restore, `x-ui`, XHTTP, WebSocket,
    `telegram-bot-simple.service`, and profile status API stayed active
  - after restore, local Reality canary passed on `443` and `2083` with
    HTTP `204`

## Deployed Files On NL

- `/etc/ghost-access/nl-https-ws-8443.json`
- `/etc/ghost-access/nl-xhttp-8443.json`
- `/etc/systemd/system/ghost-access-nl-https-ws.service`
- `/etc/systemd/system/ghost-access-nl-https-ws-sync.service`
- `/etc/systemd/system/ghost-access-nl-https-ws-sync.timer`
- `/etc/systemd/system/ghost-access-nl-xhttp.service`
- `/etc/systemd/system/ghost-access-nl-xhttp-sync.service`
- `/etc/systemd/system/ghost-access-nl-xhttp-sync.timer`
- `/opt/ghost-access-bot/current/scripts/sync_ghost_https_ws_clients.py`
- `/opt/ghost-access-bot/current/scripts/collect_transport_usage_evidence.py`
- `/opt/ghost-access-bot/current/scripts/rollback_ghost_fallbacks.py`
- `/opt/ghost-access-bot/current/telegram_bot_simple.py`
- `/opt/ghost-access-bot/shared/.env`
- `/opt/x0tta6bl4-mesh/scripts/vps_build_runtime_state.py`
- `/etc/nginx/sites-available/ghost-access-sub`
- `/var/lib/ghost-access/transport-usage/latest.json`
- `/var/lib/ghost-access/transport-usage/hash.key`
- `/etc/systemd/system/ghost-access-transport-usage-evidence.service`
- `/etc/systemd/system/ghost-access-transport-usage-evidence.timer`

## Backups

- `/opt/ghost-access-bot/current/telegram_bot_simple.py.bak-ghost-ws-20260601T202601Z`
- `/opt/ghost-access-bot/current/telegram_bot_simple.py.bak-ghost-xhttp-20260601T204802Z`
- `/opt/ghost-access-bot/current/telegram_bot_simple.py.bak-anti-block-status-20260601T212828Z`
- `/opt/ghost-access-bot/current/telegram_bot_simple.py.bak-anti-block-rollback-20260601T214535Z`
- `/opt/ghost-access-bot/shared/.env.bak-ghost-ws-20260601T202601Z`
- `/opt/ghost-access-bot/shared/.env.bak-ghost-xhttp-20260601T204802Z`
- `/opt/ghost-access-bot/shared/.env.bak-restore-fallbacks-20260601T215818Z`
- `/opt/x0tta6bl4-mesh/scripts/vps_build_runtime_state.py.bak-ghost-ws-evidence-20260601T203352Z`
- `/opt/x0tta6bl4-mesh/scripts/vps_build_runtime_state.py.bak-ghost-xhttp-evidence-20260601T205021Z`
- `/opt/x0tta6bl4-mesh/scripts/vps_build_runtime_state.py.bak-transport-usage-20260601T210116Z`
- `/opt/x0tta6bl4-mesh/scripts/vps_build_runtime_state.py.bak-usage-summary-20260601T210750Z`
- `/opt/x0tta6bl4-mesh/scripts/profile_status_api.py.bak-transport-usage-20260601T211914Z`
- `/etc/nginx/sites-available/ghost-access-sub.bak-ghost-ws-20260601T201312Z`
- `/etc/nginx/sites-available/ghost-access-sub.bak-ghost-xhttp-20260601T204453Z`
- `/opt/ghost-access-bot/current/scripts/sync_ghost_https_ws_clients.py.bak-xhttp-20260601T204426Z`

## Rollback

Check rollback plan first:

```bash
python3 /opt/ghost-access-bot/current/scripts/rollback_ghost_fallbacks.py --json
```

Delivery-only rollback disables future fallback delivery first and keeps the
fallback services running, so existing fallback sessions are not intentionally
dropped:

```bash
python3 /opt/ghost-access-bot/current/scripts/rollback_ghost_fallbacks.py \
  --apply \
  --confirm ROLLBACK_GHOST_FALLBACKS \
  --json
```

Equivalent manual delivery-only fallback disable:

```bash
sudo sed -i 's/^ENABLE_GHOST_HTTPS_WS_FALLBACK=.*/ENABLE_GHOST_HTTPS_WS_FALLBACK=0/' /opt/ghost-access-bot/shared/.env
sudo sed -i 's/^ENABLE_GHOST_XHTTP_FALLBACK=.*/ENABLE_GHOST_XHTTP_FALLBACK=0/' /opt/ghost-access-bot/shared/.env
sudo sed -i 's/^EXPOSE_FALLBACK_TRANSPORTS=.*/EXPOSE_FALLBACK_TRANSPORTS=0/' /opt/ghost-access-bot/shared/.env
sudo systemctl restart telegram-bot-simple.service
```

Only stop the standalone fallback path after checking that no users need the
fallback sessions:

```bash
python3 /opt/ghost-access-bot/current/scripts/rollback_ghost_fallbacks.py \
  --mode stop-services \
  --apply \
  --confirm ROLLBACK_GHOST_FALLBACKS \
  --service-stop-confirm STOP_GHOST_FALLBACK_SERVICES \
  --json
```

Equivalent manual service stop:

```bash
sudo systemctl disable --now ghost-access-nl-https-ws-sync.timer
sudo systemctl disable --now ghost-access-nl-https-ws.service
sudo systemctl disable --now ghost-access-nl-xhttp-sync.timer
sudo systemctl disable --now ghost-access-nl-xhttp.service
sudo systemctl disable --now ghost-access-transport-usage-evidence.timer
```

Restore nginx if needed:

```bash
sudo cp -a /etc/nginx/sites-available/ghost-access-sub.bak-ghost-ws-20260601T201312Z /etc/nginx/sites-available/ghost-access-sub
sudo nginx -t && sudo systemctl reload nginx
```

Restore bot/env if needed:

```bash
sudo cp -a /opt/ghost-access-bot/current/telegram_bot_simple.py.bak-ghost-ws-20260601T202601Z /opt/ghost-access-bot/current/telegram_bot_simple.py
sudo cp -a /opt/ghost-access-bot/shared/.env.bak-ghost-ws-20260601T202601Z /opt/ghost-access-bot/shared/.env
sudo systemctl restart telegram-bot-simple.service
```

## Remaining Work

- Keep XHTTP as the preferred fallback and monitor real client compatibility
  across v2rayN, Happ, Hiddify, and mobile networks.
- Promote the privacy-safe transport usage evidence into operator UI/admin
  commands so support can see which fallback family is actually being used.
- Stop treating `Reality TCP` as the main anti-DPI strategy; keep it as legacy
  fallback while Ghost-backed paths mature.
