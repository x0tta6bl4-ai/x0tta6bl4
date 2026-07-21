# VPN Profile Health Runbook

This runbook outlines the operational procedures for monitoring and maintaining the health of Ghost Access VPN profiles and underlying nodes.

## 1. Overview of VPN Health Monitoring

The Ghost Access health monitoring architecture relies on:
- **Prometheus**: Scrapes metrics from Xray-core nodes (NL and SPB).
- **Grafana**: Visualizes metrics and active connections.
- **Canary Probes**: External agents constantly checking connectivity via test profiles.
- **Alertmanager**: Dispatches alerts to Ops channels based on predefined thresholds.

## 2. Key Metrics and Thresholds

| Metric | Threshold / Alert Condition | Severity |
|--------|-----------------------------|----------|
| Node Uptime | Down for > 2 minutes | CRITICAL |
| CPU Usage | > 85% for 15 minutes | WARNING |
| Memory Usage | > 90% for 5 minutes | WARNING |
| Canary Test Latency | > 500ms or 100% loss | HIGH |
| Active TCP Connections | Sudden drop by > 50% | HIGH |

## 3. Alert Response Procedures

### Node Down Alert
1. SSH into the affected node (`ssh root@89.125.1.107` or `ssh sb`).
2. Check if the process is running:
   ```bash
   # For NL
   systemctl status x-ui
   # For SPB
   systemctl status xray
   ```
3. Restart if failed: `systemctl restart x-ui` (or `xray`).
4. Check kernel logs for OOM kills: `dmesg -T | grep -i oom`.

### High Latency / Packet Loss (DPI Block Suspected)
1. Verify if IP or Port is blocked using an external looking glass or ping tool from RU networks.
2. If the Reality SNI is being throttled, update the SNI in the config and push to clients via subscription update.
3. If IP is blocked, consider spinning up a new secondary ingress node.

## 4. Profile Rotation Procedures

To mitigate fingerprinting and blocks, profiles should be rotated periodically or upon detection of DPI interference.
- **Automated Rotation**: Ensure the config generator cron is active.
- **Manual Rotation**:
  ```bash
  # Update x-ui inbound settings (NL)
  # Typically done via x-ui web interface or API
  ```

## 5. Orphan UUID Cleanup

To prevent performance degradation, unused or revoked UUIDs must be purged.
```bash
# Example script to find and remove inactive UUIDs (Requires custom script)
/opt/ghost-access/scripts/cleanup-orphans.sh --dry-run
/opt/ghost-access/scripts/cleanup-orphans.sh --execute
```

## 6. Emergency Procedures

### DPI Block on Primary Node
- Immediately failover users to the fallback transport (e.g., WS CDN).
- Notify users via Telegram bot to update subscriptions.

### Certificate Expiry
- If Let's Encrypt fails to auto-renew (for WS/gRPC transports):
  ```bash
  certbot renew --force-renewal
  systemctl restart xray
  systemctl restart nginx
  ```

### Disk Full
- Identify large files (usually logs):
  ```bash
  du -ah / | grep -v "/proc" | sort -n -r | head -n 20
  ```
- Clear Xray/x-ui access logs:
  ```bash
  truncate -s 0 /var/log/xray/access.log
  ```
