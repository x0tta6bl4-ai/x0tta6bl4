# NL Legacy Client Migration Packet

- Decision: `LEGACY_CLIENT_MIGRATION_PACKET_READY`
- Operator action: `ask_legacy_clients_to_refresh_reality_profile`
- Active subscriptions: `14`
- Expired users excluded: `13`
- Safe profile: `reality` ports `[443, 2083]`
- Subscription payload safe: `True`
- Legacy attention: `True`

## Findings

- `15m:ghost_https_ws:legacy_proxy_requests_without_dataplane`
- `15m:ghost_xhttp:legacy_proxy_4xx_seen`
- `15m:ghost_xhttp:legacy_proxy_requests_without_dataplane`
- `360m:ghost_xhttp:legacy_proxy_4xx_seen`
- `60m:ghost_https_ws:legacy_proxy_requests_without_dataplane`
- `60m:ghost_xhttp:legacy_proxy_4xx_seen`
- `60m:ghost_xhttp:legacy_proxy_requests_without_dataplane`

## User Message

Если VPN сейчас не подключается, обновите профиль. Откройте этого бота, нажмите Подключить и импортируйте свежий профиль Reality. В клиенте удалите старые профили Ghost Access с xhttp, ws или портом 8443, чтобы телефон не выбирал их вместо нового профиля. После проверки ответьте только одним вариантом: done updated, fail import, fail timeout или fail no-internet. Не присылайте ссылки, QR-коды, UUID, IP-адреса, скриншоты, логи, телефон или username.

## Safe Replies

- `done updated`
- `fail import`
- `fail timeout`
- `fail no-internet`

## Reply Recording

Validate a short reply before writing:

```bash
printf '%s\n' "done updated" | python3 services/nl-server/ghost-access/record_legacy_client_migration_reply.py --expect-packet-sha256 "$(sha256sum nl-diagnostics/nl-legacy-client-migration-packet-2026-06-05.json | awk '{print $1}')" --reporter-label legacy-client-1 --reply-stdin --json
```

Record a short reply only after operator review:

```bash
printf '%s\n' "done updated" | python3 services/nl-server/ghost-access/record_legacy_client_migration_reply.py --write --expect-packet-sha256 "$(sha256sum nl-diagnostics/nl-legacy-client-migration-packet-2026-06-05.json | awk '{print $1}')" --reporter-label legacy-client-1 --reply-stdin --json
```

Change `legacy-client-1` to a non-private local label such as `legacy-client-2`.

## Send Policy

- Automatic broadcast allowed: `false`
- Manual operator review required: `true`
