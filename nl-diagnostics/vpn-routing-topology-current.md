# Current VPN Routing Topology & Performance Optimizations (2026)

## Overview & Architecture Map

```
                          ┌─────────────────┐
                          │   Интернет      │
                          └────────┬────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
              ┌─────┴─────┐  ┌────┴────┐  ┌──────┴──────┐
              │  WARP IP  │  │ NL VPS  │  │ Moscow VPS  │
              │104.28.251 │  │:443     │  │:443         │
              └───────────┘  │:10085   │  │(Reality     │
                             │:8443    │  │ SNI vk.com) │
                             └────┬────┘  └──────┬──────┘
                                  │              │
                          WS:/ghost-ws           │
                          (relay)                │
                                  │              │
                                  └──────────────┘
                                        ↑
                                    Клиенты
```

## Node Details

### 1. Moscow Entry Node (84.54.47.103) — Entry & RU Exit Point
- **Inbound:** `:443` VLESS + Reality (SNI: `vk.com`)
- **Outbounds:**
  - `direct`: freedom (Direct out from Moscow for RU IPs & RU sites)
  - `nl-beta`: VLESS + WS + TLS to `NL:8443` via `/ghost-ws`
  - `block`: blackhole
- **Routing Rules:**
  1. `UDP :443` -> `block` (Forces YouTube/Google to TCP, bypassing QUIC blocks)
  2. `DNS :53` (tcp+udp) -> `nl-beta` (All DNS routed via NL)
  3. `geoip:private` + `geoip:ru` -> `direct`
  4. `VK & RU CDNs` (`geosite:category-ru`, `geosite:vk`, `domain:vk.com`, `domain:vk.ru`, `domain:vk.me`, `domain:userapi.com`, `domain:vkuseraccess.com`, `domain:vk-cdn.net`, `domain:vk-portal.net`) -> `direct` (Exit IP: Moscow, RU)
  5. Fallback -> `nl-beta` (All non-RU traffic forwarded to NL)

---

### 2. NL Main Server (89.125.1.107) — Foreign Exit & Anti-DPI Backup
- **Inbounds:**
  - `inbound-443`: VLESS + Reality (`:443`, `:8443`, `:2083`, SNI: `samsung.com` / `vk.com`)
  - `inbound-10085`: VLESS + WS `/ghost-ws` (listening on `127.0.0.1`, relay input from Moscow)
- **Outbounds:**
  - `direct`: freedom (Direct exit from NL for all general traffic)
  - `warp`: Cloudflare WARP SOCKS5 proxy (`127.0.0.1:40000`)
  - `blocked`: blackhole
  - `fragment`: freedom + TLS fragmentation
- **Routing Rules:**
  1. Google, YouTube, OpenAI, Anthropic, GitHub, Reddit, Social Media, Freelance -> `warp` (Cloudflare IP mask: `104.28.251.x`)
  2. Telegram (Domains + IPs) -> `direct`
  3. `redd.it` -> `direct`
  4. `geoip:private` -> `blocked`
  5. BitTorrent -> `blocked`
  6. Ads -> `blocked`
  7. Direct NL clients (`inbound-443`) -> `fragment`
  8. Fallback -> `direct`

---

## Traffic Path Summary & VK Fix

```
Client (Phone / PC)
    │
    ├──→ Moscow:443 (Reality SNI vk.com)
    │        │
    │        ├── VK (vk.com, userapi.com, vk.me, vk-cdn.net) → direct → Internet from Moscow (RU IP)
    │        ├── Other RU/Private → direct → Internet from Moscow (RU IP)
    │        │
    │        └── Non-RU? → nl-beta (WS :8443) → NL
    │                              │
    │                              ├── Google/YouTube/OpenAI/Social/Freelance → WARP (Cloudflare)
    │                              ├── Telegram → direct (from NL)
    │                              ├── Ads/P2P → blocked
    │                              └── Fallback → direct (from NL)
    │
    └──→ NL:443 / NL:8443 (Reality Direct Entrance)
             │
             ├── Google/YouTube/OpenAI/Social/Freelance → WARP (Cloudflare)
             ├── Telegram → direct (from NL)
             ├── Ads/P2P → blocked
             └── Fallback → direct (from NL)
```

## VK Performance Resolution Status
- **Status:** **VERIFIED & APPLIED**
- **Changes Applied:** All VK core & media CDN domains explicitly bound to `direct` outbound in Moscow & NL Xray runtimes.
- **Client Action Needed:** Toggle VPN off and on (reconnect) on mobile clients to refresh the connection pool.
