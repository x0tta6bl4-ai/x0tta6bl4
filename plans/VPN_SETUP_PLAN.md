# VPN Setup Plan — Backward Compatibility (VPS 89.125.1.107)
**Status:** DRAFT — pending full agent consensus  
**Created:** 2026-03-10  
**Revision:** 2026-03-11  
**Rule:** No server changes until explicit owner approval.

## 1) Goal and Non-Goals
**Goal**
- Keep all existing (legacy) VLESS+Reality links working with zero user action.
- New default configs use `443` with `eh.vk.com`, `sid=b2c4`, `fp=qq`.

**Non-Goals**
- No PQC/SPIRE/mesh/eBPF/WARP/systemd hardening.
- No billing/Stripe work.
- No client-side changes required.

## 2) Current State (Read-Only Findings)
**Live inbounds (from `/etc/x-ui/x-ui.db`)**
- `443`: VLESS Reality, `target=eh.vk.com:443`, `serverNames=[eh.vk.com]`, `shortIds=[b2c4]`, `fp=qq`
- `39829`: VLESS Reality, `target=google.com:443`, `serverNames=[google.com, www.google.com]`, `shortIds=[6b,97,a1]`, `fp=qq`

**Reality key**
- Single private key across all backups (one unique key hash). Compatibility can be handled in one inbound.

**Client flow note**
- Detected **2 clients without `flow`** in x-ui inbound lists. Do **not** modify their per-client config separately; keep them as-is.

**Additional legacy config path**
- Found `/usr/local/etc/xray/config.json` with a minimal legacy inbound: `443` + `serverNames=[google.com, www.google.com]`, `shortIds=[6b]`.

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

## 4) Proposed Changes (Not Executed Yet)
**Primary approach (recommended)**
- Expand inbound `443` to include the full legacy `serverNames` and `shortIds` union.
- Keep inbound `39829` unchanged.
- Keep the same Reality private key and current `fp=qq`.

**Fallback (only if list size or constraints block primary approach)**
- Add SNI routing on `443`:
  - `eh.vk.com` -> current inbound
  - `google.com` -> legacy inbound
- Keep `39829` unchanged.

## 5) Pending: Config Generator Update (Requires Approval)
Update defaults in `vpn_config_generator.py`:
- `VPN_PORT=443`
- `REALITY_SNI=eh.vk.com`
- `REALITY_SHORT_ID=b2c4`
- `REALITY_FINGERPRINT=qq`
- `XUI_DB_PATH=/etc/x-ui/x-ui.db`

## 6) Validation Plan (Post-Approval)
- `ss -ltnp`: ensure `443` and `39829` listening.
- `openssl s_client`:
  - `SNI=eh.vk.com` -> VK certificate
  - `SNI=google.com` -> Google certificate
- Test one legacy link and one new link.

## 7) Agent Consensus (Pending)
- `claude`: OPSEC/DPI risks of expanded lists.
- `gemini`: transport stability and operational safeguards.
- `owner`: final approval before any changes.

## 8) Known Risk Outside This Plan (Do Not Trigger)
**rotate_reality_credentials() risk**
- `vpn_config_generator.py` contains a method that **overwrites** `shortIds` with a single new value.
- If invoked automatically (watchdog/self-heal), it would **break legacy links**.
- Mitigation (future change, not part of this plan): preserve existing `shortIds` and only append new ones, or gate the call behind explicit approval.
