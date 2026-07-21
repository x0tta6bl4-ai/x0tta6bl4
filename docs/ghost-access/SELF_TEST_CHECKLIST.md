# Ghost Access - Self-Test Checklist

This checklist provides a structured way to verify that the Ghost Access VPN is operating correctly on both server and client sides.

## 1. Server-Side Checks

### NL Production Server (`89.125.1.107`)
1. **Check x-ui status**:
   ```bash
   systemctl status x-ui
   ```
2. **Check Xray-core status and config**:
   ```bash
   # Config path: /usr/local/x-ui/bin/config.json
   /usr/local/x-ui/bin/xray -test -config /usr/local/x-ui/bin/config.json
   ```
3. **Check listening ports** (e.g., 443 for XTLS/Reality):
   ```bash
   netstat -tulpn | grep xray
   ```

### SPB Staging Server (`sb`)
1. **Connect to SPB node**:
   ```bash
   ssh sb
   ```
2. **Check Xray-core status and config**:
   ```bash
   # Config path: /usr/local/etc/xray/config.json
   /usr/local/bin/xray -test -config /usr/local/etc/xray/config.json
   systemctl status xray
   ```

### Shared Infrastructure Checks
- **TLS Certificates**: Ensure Let's Encrypt certificates are valid (if not using Reality):
  ```bash
  openssl x509 -in /path/to/cert.crt -text -noout | grep "Not After"
  ```

## 2. Client-Side Checks

1. **Config Import**: Verify that a test subscription link or QR code imports successfully into a compatible client (e.g., v2rayN, NekoBox).
2. **Connection Test**: Connect to the profile and check "True Delay" or ping in the client.
3. **Connectivity Verification**:
   - Open a browser and navigate to `https://1.1.1.1/help` to ensure DNS is resolving and traffic is routing.
4. **DNS Leak Test**:
   - Visit [dnsleaktest.com](https://www.dnsleaktest.com) and ensure only the VPN's DNS servers are visible.
5. **Speed Test**:
   - Run a test on [speedtest.net](https://www.speedtest.net) to confirm adequate throughput.

## 3. Monitoring Checks

1. **Prometheus Metrics**:
   - Verify that the Xray metrics endpoint is accessible and scraping successfully.
   ```bash
   curl -s http://localhost:8080/metrics | grep xray_
   ```
2. **Canary Status**:
   - Ensure external canary probes are reporting green/healthy.
3. **Telegram Bot Status**:
   - Send `/start` and `/status` to the Telegram provisioning bot to ensure it responds.

## 4. Troubleshooting Common Issues

- **Client cannot connect (Timeout)**:
  - Check if the port (e.g., 443) is blocked by DPI. Test with a different protocol (e.g., VMess+WS).
  - Verify firewall rules on the VPS: `ufw status` or `iptables -L`.
- **Reality fallback failing**:
  - Verify the target SNI domain is reachable from the server: `curl -I https://<sni-target.com>`.
- **Bot not responding**:
  - Check the bot service logs: `journalctl -u ghost-bot -f`.
