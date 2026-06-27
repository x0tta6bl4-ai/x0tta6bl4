#!/usr/bin/env bash
# scripts/ops/soak_test_monitor.sh — Periodic status logger for 24h soak test
set -euo pipefail

LOG_FILE="/opt/x0tta6bl4/logs/soak_test.log"
mkdir -p /opt/x0tta6bl4/logs

echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [INFO] Soak test heartbeat" >> "${LOG_FILE}"

# Check XDP
if bpftool prog show name xdp_mesh_filter_prog >/dev/null 2>&1; then
    echo "  XDP: ACTIVE" >> "${LOG_FILE}"
else
    echo "  XDP: FAILED" >> "${LOG_FILE}"
fi

# Check VPN
if systemctl is-active --quiet x-ui; then
    echo "  VPN: ACTIVE" >> "${LOG_FILE}"
else
    echo "  VPN: FAILED" >> "${LOG_FILE}"
fi

# Check Metrics
if curl -s localhost:9101/metrics | grep -q "x0tta6bl4_xdp_pps"; then
    echo "  METRICS: OK" >> "${LOG_FILE}"
else
    echo "  METRICS: MISSING" >> "${LOG_FILE}"
fi

# Check Open5GS
if systemctl is-active --quiet open5gs-amfd; then
    echo "  5G-CORE: OK" >> "${LOG_FILE}"
else
    echo "  5G-CORE: FAILED" >> "${LOG_FILE}"
fi

echo "----------------------------------------" >> "${LOG_FILE}"
