# NL Telegram Media WARP Route Plan - 2026-06-02

## Decision

`TELEGRAM_MEDIA_WARP_ROUTE_READY_TO_STAGE`

## Selected Bypass

route Telegram media/data-center IPv4 ranges through existing Xray WARP outbound

## Current Evidence

```json
{
  "xray_outbound_tags": [
    "direct",
    "warp",
    "blocked"
  ],
  "xray_routing_rule_count": 10,
  "telegram_media_status": "degraded",
  "warp_status": "healthy",
  "runtime_reason": "telegram media edges are slow, but VPN transport is usable"
}
```

## Target Xray Rule

```json
{
  "type": "field",
  "ip": [
    "91.108.4.0/22",
    "91.108.8.0/22",
    "91.108.12.0/22",
    "91.108.16.0/22",
    "91.108.20.0/22",
    "91.108.56.0/22",
    "149.154.160.0/20"
  ],
  "outboundTag": "warp"
}
```

## Rollout Guard

```json
{
  "applies_to": "/usr/local/x-ui/bin/config.json",
  "mutation_scope": "routing.rules only",
  "requires_explicit_operator_confirm": "APPLY_TELEGRAM_MEDIA_WARP_ROUTE",
  "requires_fresh_readonly_snapshot": true,
  "requires_config_backup": true,
  "requires_xray_config_test_before_restart": true,
  "restart_scope": [
    "x-ui"
  ],
  "forbidden_restarts": [
    "ghost-access-nl-xhttp.service",
    "ghost-access-nl-https-ws.service",
    "telegram-bot-simple.service",
    "nginx"
  ],
  "rollback": "restore config backup, run xray config test, restart x-ui once"
}
```

## Operator Steps

1. take a fresh read-only snapshot and confirm warp-svc is active plus 127.0.0.1:40000 accepts SOCKS
2. backup /usr/local/x-ui/bin/config.json
3. insert target_rule before the final direct tcp/udp catch-all rule
4. run xray -test against the staged config
5. restart only x-ui in a maintenance window
6. test Telegram media through client profiles and compare direct vs WARP egress
7. rollback from backup if Telegram media or normal browsing regresses
