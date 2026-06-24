Quarantine

These client examples are intentionally disabled because current external
reachability checks did not prove them usable for real users.

Known current state:
- 443 VLESS Reality: distributable.
- 8443 VLESS xHTTP/splitHTTP: public port is open but reaches a different TLS
  service than local Xray.
- 9443 Trojan: public port is not reachable.
- 8388 Shadowsocks: public port is not reachable.
- 8080 VMess/WebSocket: public port is not reachable.

Move a profile out of this directory only after scripts/validate-installation.sh
passes the external reachability check for that exact transport and port.
