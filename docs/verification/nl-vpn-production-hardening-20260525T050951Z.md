# NL VPN Production Hardening Proof

Timestamp: `2026-05-25T05:09:51Z`

Scope:

- NL VPN endpoint: `89.125.1.107`
- Local tunnel interface: `singbox_tun`
- Local SOCKS5 proxy: auto-detected as `127.0.0.1:10918`

## Result

PASS for this local production hardening pass.

No xray or sing-box data-path process was restarted by the verification pass.
Only `x0tta-node.service` was restarted to load the safer
`VPN_SELF_HEAL_ENABLE=false` default in `self_healing_daemon.py`.

## Evidence

Local reproducible health-check:

```text
bash scripts/vpn_status.sh --check
Result: PASS (warnings=0)
```

Route-loop check:

```text
ip route get 89.125.1.107
89.125.1.107 via 192.168.0.1 dev enp8s0 src 192.168.0.104

ip route get 1.1.1.1
1.1.1.1 via 172.18.0.2 dev singbox_tun table 2022 src 172.18.0.1
```

False-healing guardrails:

```text
systemctl status --no-pager --lines=20 x0tta-node.service
Started monitoring interface singbox_tun -> target 8.8.8.8 ... | heal_enabled=False

curl -fsS http://127.0.0.1:9091/metrics
vpn_heal_total 0
vpn_proxy_failure_streak 0
vpn_packet_loss_failure_streak 0
vpn_stale_state_failure_streak 0
```

Manual heal preflight:

```text
bash scripts/vpn_heal.sh
Preflight: FIN-WAIT-2=0 CLOSE-WAIT=0 proxy=ok
No heal needed. Set VPN_HEAL_FORCE=1 to reload xray anyway.
```

Rollback dry-run:

```text
bash scripts/rollback_nl_vpn_route_bypass.sh --dry-run
Mode: dry-run
x0tta-vpn-route-bypass.service: active
x0tta-vpn-watchdog.service: active
ip rule: 8999: from all to 89.125.1.107 lookup main
route: 89.125.1.107 via 192.168.0.1 dev enp8s0
Rollback command completed.
```

Focused tests:

```text
python3 -m py_compile src/network/vpn_watchdog.py src/network/self_healing_daemon.py
bash -n scripts/vpn_status.sh scripts/vpn_heal.sh scripts/apply_vpn_route_bypass.sh scripts/rollback_nl_vpn_route_bypass.sh
PYTEST_ADDOPTS=--no-cov python3 -m pytest tests/unit/network/test_vpn_health_autodetect_unit.py -q
12 passed in 0.88s
```

## Files Changed

- `src/network/self_healing_daemon.py`
- `src/network/vpn_watchdog.py`
- `scripts/vpn_status.sh`
- `scripts/vpn_heal.sh`
- `scripts/apply_vpn_route_bypass.sh`
- `scripts/rollback_nl_vpn_route_bypass.sh`
- `docs/runbooks/NL_VPN_HEALTH.md`
- `tests/unit/network/test_vpn_health_autodetect_unit.py`
