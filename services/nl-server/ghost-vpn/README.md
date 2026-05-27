# NL Ghost VPN Source Candidates

Priority source candidates from NL:

```text
ghost_vpn_server.py
ghost_vpn_client.py
ghost_vpn_protocol.py
ghost_tcp_bridge.py
```

These files exist on NL and are only partially restored in this local source
area. Pull remaining files only into quarantine first, then run secret review
and local import/syntax tests before promoting them here.

Reviewed source now copied here:

```text
ghost_vpn_protocol.py
ghost_tcp_bridge.py
ghost_vpn_server.py
ghost_vpn_client.py
```

`ghost_tcp_bridge.py` matches the current NL source hash and has local tests for
UDP-to-TCP frame encoding. `ghost_vpn_protocol.py` has an intentional local
import fallback and is therefore not a byte-for-byte deploy source. Nothing here
is deployed while NL is read-only.

`ghost_vpn_server.py` and `ghost_vpn_client.py` match the current NL source
hashes, but they are class C runtime tools: running them can create TUN
interfaces and change `ip route`, `ip rule`, `sysctl` and `iptables`. They need
explicit mutation gates before any deploy or live run.
