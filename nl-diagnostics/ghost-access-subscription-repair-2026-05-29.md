# Ghost Access Subscription Repair - 2026-05-29

Status: repaired on NL.

Observed complaint:

- VPN client reported `Подписка не найдена (HTTP 404)`.
- Screenshot profile label was an offline Ghost Access subscription.
- Phone-visible time was consistent with nginx access log requests around
  `2026-05-29 08:31 UTC`.

Server findings:

- `nl` SSH host: `89.125.1.107`.
- Live DB: `/opt/ghost-access-bot/shared/x0tta6bl4.db`.
- nginx `/sub/...` proxy path was working for valid live DB tokens.
- The failing client used `v2raytun/android`.
- Failing subscription token prefix: `811SLS...`, length `32`.
- Xray access log tied the same client IP to
  `offline-offline-lbez82@x0tta6bl4`.
- Current DB row `OFFLINE-LBEZ82` existed, but had an expired date
  `2026-05-18T10:39:39.367547` and a different token prefix.

Action taken:

- Created SQLite backup on NL:
  `/opt/ghost-access-bot/shared/backups/x0tta6bl4.subscription-repair-offline-lbez82-20260529T095243Z.db`
- Updated `offline_subscriptions` row `OFFLINE-LBEZ82`:
  - `subscription_token`: restored to failing client token prefix `811SLS...`
  - `plan`: `basic_12m`
  - `days`: `365`
  - `expires_at`: `2027-05-25T12:12:00`

Verification:

- Before update, external HTTPS subscription check returned `404`.
- After update, the same external HTTPS subscription check returned `200`.
- Response included:
  - `subscription-userinfo` with future expiry epoch.
  - `x-primary-uuid` prefix matching the `OFFLINE-LBEZ82` VPN UUID.

No full subscription token is stored in this note.
