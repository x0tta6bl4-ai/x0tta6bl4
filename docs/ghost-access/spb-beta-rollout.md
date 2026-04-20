# SPB Beta Bridge Rollout

Updated: 2026-04-20

## Status

**Phase 5 (Ghost backend canary) reached on 2026-04-19.** SPB entry node and
NL Ghost backend pair are both `active`. Beta scope expanded by codex beyond
the original "1-3 manual links" plan (see _Actual state vs original plan_
below). No bot integration yet — subscription links for paying users still
point to NL `89.125.1.107`.

## Goal (unchanged)

Bring up a new St. Petersburg entry node at `195.58.48.193` and chain it to the
current Netherlands exit node at `89.125.1.107` without changing the current
Ghost Access delivery path for existing users.

## Current production baseline (NL)

- Exit node: `89.125.1.107`
- Live user-facing Reality inbounds on NL:
  - `443` remark `VLESS-VK-443` (99 clients in xray config as of 2026-04-20)
  - `2083` remark `VLESS-Optimized-2083` (44 clients)
  - `39829` legacy Reality (41 clients)
- Subscription HTTP server on NL:
  - port `8880`
  - `SUBSCRIPTION_BASE_URL=https://89-125-1-107.sslip.io:8443`
- Shared Ghost Access DB on NL:
  - `/opt/ghost-access-bot/shared/x0tta6bl4.db`

## Isolation rules

- Do not change `VPN_SERVER` or `SUBSCRIPTION_BASE_URL` in the current bot.
- `PROFILE_VPN_SERVER` must default to `VPN_SERVER` (NL) — see
  `.claude/rules/50-prod-source-of-truth.md`.
- Do not modify existing user subscriptions.
- Do not reuse NL production ports `443`, `2083`, `39829`, `8443`, `8880`.
- Beta users must be issued manually first.
- SPB beta must be validated with raw links before any bot integration.

## Actual state vs original plan (2026-04-20 reconciliation)

The original plan called for NL beta inbound on `2443/tcp` as the rollback
backend, and a small canary set on SPB. Actual deployed topology diverges:

| Item | Original plan | Actual state |
|---|---|---|
| NL beta inbound `2443/tcp` | required | **not listening** (never deployed) |
| `ghost-access-nl-beta.service` | preferred | **does not exist** |
| SPB entry ports | `443, 2083, 8443` | `443, 2083, 8443, 2053, 2087, 2096` |
| SPB canary inbounds | none | `entry-canary-21443` (port 21443), `entry-canary-2052` (port 2052) |
| SPB→NL Ghost backend | planned | **active**: `tun_ghost_c` `10.8.0.2/24`, RTT ~33 ms |
| SPB→NL fallback path | NL beta `2443` | **none** (Ghost-only via `ghost-canary` outbound) |
| Manual beta links | 1-3 | 12 real users overlap with bot DB, plus 17 orphan UUIDs on `entry-443` not tracked in `x0tta6bl4.db` |

## Live SPB topology (verified 2026-04-20)

```text
beta client (Happ / Hiddify / v2rayN)
  -> SPB Reality inbound (443 / 2083 / 8443 / 2053 / 2087 / 2096)
     -> direct (geoip:private, geoip:ru, geosite:ru and RU domain whitelist)
     -> ghost-canary outbound (freedom proto, sendThrough 10.8.0.2 via tun_ghost_c)
        -> NL Ghost backend (UDP)
           -> open internet
```

`nl-beta` outbound (Reality to NL `2443`) exists in xray config but routes
nothing because NL `2443` is not listening. Effective backend for non-RU
traffic is Ghost over `tun_ghost_c`.

## Live SPB inbound table

| Tag | Port | Protocol | Clients (2026-04-20) |
|---|---|---|---|
| `entry-443` | 443 | vless+reality | 29 (12 mapped to bot users, **17 orphans**) |
| `entry-8443` | 8443 | vless+reality | 1 |
| `entry-2053` | 2053 | vless+reality | 1 |
| `entry-2083` | 2083 | vless+reality | 1 |
| `entry-2087` | 2087 | vless+reality | 1 |
| `entry-2096` | 2096 | vless+reality | 1 |
| `entry-canary-21443` | 21443 | vless+reality | 1 |
| `entry-canary-2052` | 2052 | vless+reality | 1 |
| `socks-test` | 10808 (loopback) | socks | 0 |

## Live SPB outbound table

| Tag | Protocol | Use |
|---|---|---|
| `direct` | freedom | RU + private destinations |
| `ghost-canary` | freedom (`sendThrough: 10.8.0.2`) | foreign destinations via NL Ghost UDP |
| `nl-beta` | vless+reality (NL `2443`) | **dead path** — NL `2443` not listening |
| `block` | blackhole | rejected |

13 routing rules split across `entry-443`, `entry-canary-2052`,
`entry-canary-21443` (each: RU/private → direct, foreign → `ghost-canary`).
Other entries fall through to `nl-beta` (currently dead).

## Live services

- SPB:
  - `xray.service` — `active`, `loglevel=warning` on disk, in-memory still
    `debug` until next natural restart
  - `ghost-access-spb-backend.service` — `active`,
    `tun_ghost_c 10.8.0.2/24`, RTT ~33 ms to NL
- NL:
  - `telegram-bot-simple.service` — `active`, release `20260412T065408Z`
  - `x-ui.service` — `active` (xray runs as child)
  - `ghost-access-nl-beta.service` — **does not exist** (was in original plan)

## Validation checklist (current truth)

- NL:
  - [x] `telegram-bot-simple` active
  - [x] `x-ui` active
  - [ ] `ss -ltnp` shows `:2443` — **NO**, never deployed
  - [ ] `ufw status` shows `2443/tcp ALLOW` — **NO**
  - [ ] `ghost-access-nl-beta.service` is `active` — **NO**, never deployed
- SPB:
  - [x] `ss -ltnp` shows `:443`, `:2083`, `:8443`, `:2053`, `:2087`, `:2096`,
    `:21443`, `:2052`, `:10808` (loopback)
  - [x] `xray -test -config /usr/local/etc/xray/config.json` passes
  - [x] `systemctl is-active xray` returns `active`
  - [x] `systemctl is-active ghost-access-spb-backend` returns `active`
  - [x] `ip addr show tun_ghost_c` shows `10.8.0.2/24`
- End-to-end:
  - [x] existing production users remain unchanged (NL :443 path untouched)
  - [ ] beta client raw-link QA across Hiddify / v2rayTun / Happ — partial,
    JustHost reactive ingress filter intermittently closes random SPB ports
  - [ ] `https://ifconfig.me` through full beta path resolves to NL exit IP — pending
  - [ ] `ozon.ru` / `sber.ru` reachable through SPB direct — pending
  - [ ] no overlap between SPB `entry-443` clients and bot DB — **17 orphan
    UUIDs present**, cleanup pending (needs xray restart on SPB → user
    approval required because of JustHost filter risk)

## Known blockers

- **JustHost reactive ingress filter** intermittently closes random SPB ports
  (e.g. `:443` showed CLOSED from external during burst tests, `:8443` open).
  Not fixable from VPS side. Restarts on SPB are risky because the filter may
  re-trigger after the new socket binds.
- 17 orphan UUIDs on `entry-443`: injected directly into xray config without
  corresponding row in `x0tta6bl4.db users.vpn_uuid`. Cleanup deferred until
  user approves an xray restart on SPB.

## Open work

1. Decide on `nl-beta` (`2443`) outbound — either deploy
   `ghost-access-nl-beta.service` to make it a real backup path, or remove it
   from SPB xray config to stop confusing the topology.
2. Audit and remove the 17 SPB `entry-443` orphan UUIDs (claude lane;
   needs user approval for SPB xray restart).
3. Per-user entry-node selection in the bot before any paying user is moved
   to SPB.
4. Document Ghost backend protocol details (handshake, key rotation,
   `--no-route` mode) in a sibling doc once stable.

## Owning lane

- Live runtime changes: claude (per `.claude/rules/50-prod-source-of-truth.md`).
- Bot UX / subscription delivery: `bot-product-flow`.
- SPB xray client lifecycle: `vpn-runtime-ops`.
- Codex must NOT make further direct edits to SPB xray config or the Ghost
  backend service (past incident: scope creep + PROFILE_VPN_SERVER hotfix
  required).
