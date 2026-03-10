# VPN Setup Plan — Backward Compatibility (VPS 89.125.1.107)
**Status:** ITERATION 2 COMPLETE
**Created:** 2026-03-10
**Revision:** 2026-03-11
**Rule:** No server changes without explicit owner approval.

## 1) Goal and Non-Goals
**Goal**
- Keep all existing (legacy) VLESS+Reality links working with zero user action.
- New default configs use `443` with `eh.vk.com`, `sid=b2c4`, `fp=qq`.

**Non-Goals**
- No PQC/SPIRE/mesh/eBPF/WARP changes.
- No billing/Stripe work.
- No client-side changes required.

## 2) Current State (Read-Only Findings)
**Live inbounds (from `/etc/x-ui/x-ui.db`)**
- `443`: VLESS Reality, `target=eh.vk.com:443`, `serverNames=[eh.vk.com]`, `shortIds=[b2c4]`, `fp=qq`
- `39829`: VLESS Reality, `target=google.com:443`, `serverNames=[google.com, www.google.com]`, `shortIds=[6b,97,a1]`, `fp=qq`

**Reality key**
- Single private key across all backups (one unique key hash). Compatibility handled in one inbound.

**Client flow note**
- Detected **2 clients without `flow`** in x-ui inbound lists. Not modified — kept as-is.

**Additional legacy config path**
- Found `/usr/local/etc/xray/config.json` with minimal legacy inbound: `443` + `serverNames=[google.com, www.google.com]`, `shortIds=[6b]`.

## 3) Legacy Parameter Union (Backups + /etc/xray + Live)
**PORT 443 (legacy + live)**
- `targets`: `google.com:443`, `eh.vk.com:443`
- `serverNames`:
  - `amazon.com`, `apple.com`, `cloudflare.com`, `eh.vk.com`, `facebook.com`, `github.com`,
    `google.com`, `microsoft.com`, `netflix.com`, `www.amazon.com`, `www.apple.com`,
    `www.cloudflare.com`, `www.facebook.com`, `www.github.com`, `www.google.com`,
    `www.microsoft.com`, `www.netflix.com`
- `shortIds`:
  - `0c`, `1b`, `1e`, `2b`, `2f`, `3a`, `3f`, `4a`, `4f`, `5d`, `5f`,
    `6b`, `6c`, `6e`, `7a`, `7e`, `8c`, `8e`, `97`, `9c`, `9d`, `9f`,
    `a1`, `a6`, `a8`, `b2c4`, `b3`, `b9`, `c7`, `d2`, `d4`, `e2`,
    `e5`, `eb`, `f1`, `f8`

**PORT 39829 (legacy + /etc/xray)**
- `targets`: `google.com:443`, `www.google.com:443`
- `serverNames`:
  - `amazon.com`, `apple.com`, `cloudflare.com`, `dl.google.com`, `facebook.com`,
    `fonts.googleapis.com`, `github.com`, `google.com`, `microsoft.com`, `netflix.com`,
    `www.amazon.com`, `www.apple.com`, `www.cloudflare.com`, `www.facebook.com`,
    `www.github.com`, `www.google.com`, `www.microsoft.com`, `www.netflix.com`
- `shortIds`:
  - `0c`, `1b`, `1e`, `2b`, `2f`, `3a`, `3f`, `4a`, `4f`, `5d`, `5f`,
    `6b`, `6c`, `6e`, `7a`, `7e`, `8c`, `8e`, `97`, `9c`, `9d`, `9f`,
    `a1`, `a6`, `a8`, `b3`, `b9`, `c7`, `d2`, `d4`, `e2`,
    `e5`, `eb`, `f1`, `f8`, `18e154a0558d9263`

## 4) Iteration 1 — DONE
- [x] inbound `443` expanded: 17 serverNames + 36 shortIds (live on VPS, backup at `/etc/x-ui/x-ui.db.bak.20260310_210932`)
- [x] inbound `39829` — unchanged
- [x] Reality private key — unchanged, `fp=qq` — unchanged
- [x] git history cleaned of xray secret keys (filter-repo, force-pushed)
- [x] `.gitignore` updated (xray configs, tokens, certs)

## 5) vpn_config_generator.py — DONE
- [x] Defaults: `REALITY_SNI=eh.vk.com`, `REALITY_SHORT_ID=b2c4`, `REALITY_FINGERPRINT=qq`, `XUI_DB_PATH=/etc/x-ui/x-ui.db`
- [x] `rotate_reality_credentials()` bug fixed: appends to shortIds list (max 50), never overwrites
- [x] Unit tests: `tests/unit/api/test_vpn_config_generator_unit.py` (91 lines, covers rotation)
- Committed as codex-implementer (b20d6155, bcba186e)

## 6) Iteration 2 — DONE
**T-4: VPN Watchdog systemd service**
- [x] `/etc/systemd/system/vpn-watchdog.service` — active (running), PID 80906
- [x] Prometheus metrics on `:9093`
- [x] `vpn_proxy_healthy=0` expected (SOCKS5 :10808 is client-side only)
- [x] xray SIGHUP uses process name `xray-linux-amd64` — graceful failure on mismatch, non-critical

**T-5: rc.local → systemd migration**
- [x] rc.local did not exist on server (no ogstun interface, no rc.local rules to migrate)
- [x] `iptables-persistent` installed and enabled

**T-6: SSH hardening + Grafana TLS**
- [x] SSH already hardened: `PermitRootLogin prohibit-password`, `PasswordAuthentication no`
- [ ] Grafana TLS: **deferred** — Grafana not installed on server, no Let's Encrypt cert
  - When Grafana is needed: install grafana + certbot, add nginx site with SSL termination

## 7) Known Risk
**rotate_reality_credentials() — MITIGATED**
- Bug fixed: now appends shortIds (max 50), never overwrites existing ones
- Do NOT call this automatically from watchdog without explicit approval

## 8) Agent Consensus — FINAL
- `claude`: reviewed, executed, committed — DONE
- `gemini`: reviewed T-3/T-4, synced
- `codex`: implemented T-1/T-2/T-3
- `owner`: approved Iterations 1 and 2
